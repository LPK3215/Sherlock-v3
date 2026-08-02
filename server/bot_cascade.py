"""Cascade (STT → VLM → TTS) pipeline for AI voice/video dialogs.

Pipecat 1.7 API.  Every component can be swapped independently via environment
variables — switch between local (free) and API providers on the fly.

Pipeline:
  transport.input → STT → user_aggregator → VLM → TTS → transport.output → assistant_aggregator

Providers:
  STT  : whisper (local) | funasr (local) | moonshine (local) | openai (API)
  VLM  : minicpm (API) | openai (API)
  TTS  : kokoro (local) | piper (local) | openai (API)
"""

from __future__ import annotations

import os
from importlib import import_module
from typing import Optional

from dotenv import load_dotenv
from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import UserImageRequestFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.runner.utils import get_transport_client_id
from pipecat.workers.runner import WorkerRunner

# Lazy imports — only loaded when a specific provider is selected.
# This avoids crash-on-import when a provider's optional deps are missing.
# ----------------------------------------------------------------------

def _lazy(module_path: str, class_name: str):
    """Import a class lazily, with a clear error if deps are missing."""
    try:
        m = import_module(module_path)
        return getattr(m, class_name)
    except ImportError as e:
        raise ImportError(
            f"Cannot load {class_name}: {e}. "
            f"Install with: pip install 'pipecat-ai[{module_path.split('.')[-1]}]' "
            f"or see docs at https://docs.pipecat.ai"
        ) from e

# Always needed (part of pipecat core / openai extra):
from pipecat.services.openai.llm import OpenAILLMService  # noqa: E402
from pipecat.services.openai.stt import OpenAISTTService  # noqa: E402
from pipecat.services.openai.tts import OpenAITTSService  # noqa: E402

# ---- helpers ------------------------------------------------------------------


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _require(key: str) -> str:
    value = _env(key)
    if not value:
        raise RuntimeError(f"Missing required env var: {key}")
    return value


# ---------------------------------------------------------------------------
# visual tools  (camera / screen capture on demand)
# ---------------------------------------------------------------------------

_STORED_USER_ID: Optional[str] = None
_CASCADE_VLM: Optional[OpenAILLMService] = None


async def _request_image(
    params,
    *,
    video_source: str,
) -> None:
    """Push a UserImageRequestFrame upstream so the transport captures a frame."""
    user_id = _STORED_USER_ID or params.llm.provider_state.get("_cascade_user_id", "")
    if _CASCADE_VLM:
        await _CASCADE_VLM.push_frame(
            UserImageRequestFrame(
                user_id=user_id or "",
                text=params.arguments.get("question", ""),
                append_to_context=True,
                video_source=video_source,
                function_name=params.function_name,
                tool_call_id=params.tool_call_id,
                result_callback=params.result_callback,
            ),
            FrameDirection.UPSTREAM,
        )


async def fetch_camera_image(params) -> None:
    """Tool: capture a camera frame before answering a visual question."""
    await _request_image(params, video_source="camera")


async def fetch_screen_image(params) -> None:
    """Tool: capture a screen-share frame before answering a visual question."""
    await _request_image(params, video_source="screenVideo")


CASCADE_TOOLS = ToolsSchema(
    standard_tools=[
        FunctionSchema(
            name="fetch_camera_image",
            description=(
                "Before answering a question about what the user is showing on "
                "camera, call this tool to capture the latest camera frame. "
                "Always include the user's original question as the 'question' parameter."
            ),
            properties={
                "question": {
                    "type": "string",
                    "description": "The user's visual question to answer.",
                }
            },
            required=["question"],
        ),
        FunctionSchema(
            name="fetch_screen_image",
            description=(
                "Before answering a question about what the user is sharing on "
                "their screen, call this tool to capture the latest screen frame."
            ),
            properties={
                "question": {
                    "type": "string",
                    "description": "The user's question about the screen content.",
                }
            },
            required=["question"],
        ),
    ]
)

CASCADE_SYSTEM_PROMPT = (
    "You are a friendly, helpful AI assistant with vision capabilities. "
    "You can see the user's camera and screen when they share it. "
    "When the user asks about something visual, use the fetch_camera_image "
    "or fetch_screen_image tool first to capture the latest frame, then "
    "answer based on what you see. "
    "Keep answers concise and conversational — the user is talking to you, not reading a report. "
    "Respond in the same language the user is speaking (Chinese or English)."
)


# ===========================================================================
# STT service factory
# ===========================================================================

# Provider keys:
#   whisper  → WhisperSTTService   (local, free, CPU/CUDA)
#   funasr   → FunASRSTTService    (local, free, best for Chinese)
#   moonshine→ MoonshineSTTService (local, free, CPU only, lightweight)
#   openai   → OpenAISTTService    (API, needs key)


def _make_stt_service():
    provider = _env("CASCADE_STT_PROVIDER", "whisper").lower()
    logger.info(f"Cascade STT provider: {provider}")

    if provider == "whisper":
        WhisperSTTService = _lazy("pipecat.services.whisper.stt", "WhisperSTTService")
        model = _env("CASCADE_STT_WHISPER_MODEL", "tiny")
        device = _env("CASCADE_STT_WHISPER_DEVICE", "cpu")
        compute_type = _env("CASCADE_STT_WHISPER_COMPUTE_TYPE", "int8")
        stt = WhisperSTTService(
            settings=WhisperSTTService.Settings(model=model),
            device=device,
            compute_type=compute_type,
            name="STT(Whisper)",
        )
        logger.info(
            f"  whisper model={model} device={device} compute_type={compute_type}"
        )

    elif provider == "funasr":
        FunASRSTTService = _lazy("pipecat.services.funasr.stt", "FunASRSTTService")
        device = _env("CASCADE_STT_FUNASR_DEVICE", "cpu")
        stt = FunASRSTTService(
            device=device,
            name="STT(FunASR)",
        )
        logger.info(f"  FunASR device={device}")

    elif provider == "moonshine":
        MoonshineSTTService = _lazy("pipecat.services.moonshine.stt", "MoonshineSTTService")
        stt = MoonshineSTTService(name="STT(Moonshine)")
        logger.info("  Moonshine (CPU ONNX)")

    elif provider == "openai":
        base_url = _env("CASCADE_STT_OPENAI_BASE_URL") or None
        model = _env("CASCADE_STT_OPENAI_MODEL", "whisper-1")
        stt = OpenAISTTService(
            model=model,
            api_key=_require("CASCADE_STT_OPENAI_API_KEY"),
            base_url=base_url,
            name="STT(OpenAI)",
        )
        logger.info(f"  OpenAI model={model}")

    else:
        raise RuntimeError(
            f"Unknown CASCADE_STT_PROVIDER '{provider}'. "
            f"Supported: whisper, funasr, moonshine, openai"
        )

    return stt


# ===========================================================================
# VLM service factory
# ===========================================================================

# Provider keys:
#   minicpm → MiniCPM-O API   (free public key, OpenAI compatible)
#   openai  → OpenAILLMService (API, needs key)


def _make_vlm_service() -> OpenAILLMService:
    provider = _env("CASCADE_VLM_PROVIDER", "openai").lower()
    logger.info(f"Cascade VLM provider: {provider}")

    if provider == "minicpm":
        # ---- MiniCPM cloud API (OpenAI-compatible) ----
        api_key = _require("CASCADE_VLM_MINICPM_API_KEY")
        base_url = _env(
            "CASCADE_VLM_MINICPM_BASE_URL",
            "https://api.modelbest.cn/v1",
        )
        model = _env("CASCADE_VLM_MINICPM_MODEL", "MiniCPM-O-4.5-9B")
        vlm = OpenAILLMService(
            settings=OpenAILLMService.Settings(model=model),
            api_key=api_key,
            base_url=base_url,
            name="VLM(MiniCPM-O)",
        )
        logger.info(f"  MiniCPM model={model}")

    elif provider == "openai":
        base_url = _env("CASCADE_VLM_OPENAI_BASE_URL") or None
        model = _env("CASCADE_VLM_OPENAI_MODEL", "gpt-4o")
        vlm = OpenAILLMService(
            settings=OpenAILLMService.Settings(model=model),
            api_key=_require("CASCADE_VLM_OPENAI_API_KEY"),
            base_url=base_url,
            name="VLM(OpenAI)",
        )
        logger.info(f"  OpenAI model={model}")

    else:
        raise RuntimeError(
            f"Unknown CASCADE_VLM_PROVIDER '{provider}'. "
            f"Supported: minicpm, openai"
        )

    return vlm


# ===========================================================================
# TTS service factory
# ===========================================================================

# Provider keys:
#   kokoro → KokoroTTSService (local, free)
#   piper  → PiperTTSService  (local, free)
#   openai → OpenAITTSService (API, needs key)


def _make_tts_service():
    provider = _env("CASCADE_TTS_PROVIDER", "piper").lower()
    logger.info(f"Cascade TTS provider: {provider}")

    if provider == "kokoro":
        KokoroTTSService = _lazy("pipecat.services.kokoro.tts", "KokoroTTSService")
        voice = _env("CASCADE_TTS_KOKORO_VOICE", "af_sky")
        tts = KokoroTTSService(
            settings=KokoroTTSService.Settings(voice=voice),
            name="TTS(Kokoro)",
        )
        logger.info(f"  Kokoro voice={voice}")

    elif provider == "piper":
        PiperTTSService = _lazy("pipecat.services.piper.tts", "PiperTTSService")
        voice = _env("CASCADE_TTS_PIPER_VOICE", "zh_CN-huayan-medium")
        tts = PiperTTSService(
            settings=PiperTTSService.Settings(voice=voice),
            name="TTS(Piper)",
        )
        logger.info(f"  Piper voice={voice}")

    elif provider == "openai":
        base_url = _env("CASCADE_TTS_OPENAI_BASE_URL") or None
        model = _env("CASCADE_TTS_OPENAI_MODEL", "tts-1")
        voice = _env("CASCADE_TTS_OPENAI_VOICE", "alloy")
        tts = OpenAITTSService(
            model=model,
            api_key=_require("CASCADE_TTS_OPENAI_API_KEY"),
            base_url=base_url,
            voice=voice,
            name="TTS(OpenAI)",
        )
        logger.info(f"  OpenAI model={model} voice={voice}")

    else:
        raise RuntimeError(
            f"Unknown CASCADE_TTS_PROVIDER '{provider}'. "
            f"Supported: kokoro, piper, openai"
        )

    return tts


# ---------------------------------------------------------------------------
# main entry point  (called from bot.py launcher)
# ---------------------------------------------------------------------------


async def run_bot_cascade(transport, runner_args):
    """Build and run the cascade pipeline."""
    global _CASCADE_VLM, _STORED_USER_ID

    load_dotenv(override=True)

    # -- services --
    stt = _make_stt_service()
    vlm = _make_vlm_service()
    tts = _make_tts_service()
    _CASCADE_VLM = vlm

    # -- LLM context (Pipecat 1.7 API) --
    context = LLMContext(
        messages=[
            {"role": "system", "content": CASCADE_SYSTEM_PROMPT},
            {
                "role": "assistant",
                "content": "Hi! I'm a vision-capable AI assistant. You can show me things on your camera or share your screen—just ask!",
            },
        ],
        tools=CASCADE_TOOLS,
    )

    # -- VAD --
    vad = SileroVADAnalyzer(
        params=VADParams(stop_secs=0.8, start_secs=0.2, confidence=0.4)
    )

    # -- context aggregators (realtime_service_mode=False = cascade) --
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        realtime_service_mode=False,
        user_params=LLMUserAggregatorParams(vad_analyzer=vad),
    )

    # -- register tools --
    vlm.register_function("fetch_camera_image", fetch_camera_image)
    vlm.register_function("fetch_screen_image", fetch_screen_image)

    # -- pipeline --
    pipeline = Pipeline(
        [
            transport.input(),         # microphone + camera
            stt,                        # speech → text
            user_aggregator,           # aggregate user turns (VAD)
            vlm,                        # vision-language model
            tts,                        # text → speech
            transport.output(),        # speaker
            assistant_aggregator,      # aggregate assistant turns
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        # A browser session must stay usable until the user disconnects. The
        # runner default is 300 seconds, which silently killed idle sessions.
        idle_timeout_secs=None,
    )
    logger.info("Cascade session idle timeout disabled")

    # -- track user id for visual tools --
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        global _STORED_USER_ID
        _STORED_USER_ID = get_transport_client_id(transport, client)
        logger.info(f"Cascade client connected: user_id={_STORED_USER_ID}")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Cascade client disconnected")
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)
    await runner.run()
