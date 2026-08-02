"""Switchable realtime and cascade AI video-call pipelines."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.evals.transport import EvalTransportParams
from pipecat.frames.frames import (
    InputAudioRawFrame,
    InputImageRawFrame,
    InputTextRawFrame,
    LLMRunFrame,
    OutputAudioRawFrame,
    UserImageRequestFrame,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    AssistantTurnStoppedMessage,
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
    UserTurnStoppedMessage,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import (
    create_transport,
    get_transport_client_id,
    maybe_capture_participant_camera,
    maybe_capture_participant_screen,
)
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.google.stt import GoogleSTTService
from pipecat.services.google.tts import GoogleTTSService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.realtime.events import (
    AudioConfiguration,
    AudioInput,
    AudioOutput,
    InputAudioNoiseReduction,
    InputAudioTranscription,
    SemanticTurnDetection,
    SessionProperties,
)
from pipecat.services.openai.realtime.llm import OpenAIRealtimeLLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.services.qwen.llm import QwenLLMService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

from model_config import (
    AIModelConfig,
    ModelConfigurationError,
    RealtimeModelConfig,
    ServiceModelConfig,
    load_model_config,
)
from profiles import (
    ProfileConfigurationError,
    SessionProfile,
    assemble_pipeline_processors,
    parse_session_profile,
)

load_dotenv(override=True)

SYSTEM_PROMPT = """You are a real-time AI video-call assistant. Reply in the language used by
the user. Keep answers concise and natural. Your responses will be spoken aloud, so avoid emojis,
bullet points, or formatting that cannot be spoken.

When video is available, describe only details supported by the current image. If evidence is
unclear, ask the user to move the camera, improve lighting, or share a clearer screen. Never claim
to see an object or text that is not visible."""

CASCADE_VISUAL_INSTRUCTION = """

You receive ordinary speech as text. For every question that depends on the current camera image,
call fetch_camera_image before answering. For every question that depends on the shared screen,
call fetch_screen_image before answering. Do not answer a visual question from an old image or by
guessing. The media tools automatically select the currently connected participant."""


@dataclass(slots=True)
class SessionResources:
    user_id: str | None = None


def _connected_user_id(params: FunctionCallParams) -> str | None:
    resources = params.app_resources
    return resources.user_id if isinstance(resources, SessionResources) else None


async def _request_image(
    params: FunctionCallParams,
    *,
    user_id: str,
    question: str,
    video_source: str,
) -> None:
    logger.info(
        "Visual snapshot requested | source={} user_id={} question={}",
        video_source,
        user_id,
        question,
    )
    await params.llm.push_frame(
        UserImageRequestFrame(
            user_id=user_id,
            text=question,
            append_to_context=True,
            video_source=video_source,
            function_name=params.function_name,
            tool_call_id=params.tool_call_id,
            result_callback=params.result_callback,
        ),
        FrameDirection.UPSTREAM,
    )


async def fetch_camera_image(params: FunctionCallParams, question: str):
    """Fetch a current camera image before answering a visual question.

    Args:
        question: The visual question to answer from the current camera image.
    """
    user_id = _connected_user_id(params)
    if not user_id:
        await params.result_callback({"error": "The camera participant is not connected yet."})
        return
    await _request_image(
        params,
        user_id=user_id,
        question=question,
        video_source="camera",
    )


async def fetch_screen_image(params: FunctionCallParams, question: str):
    """Fetch a current shared-screen image before answering a screen question.

    Args:
        question: The visual question to answer from the current shared screen.
    """
    user_id = _connected_user_id(params)
    if not user_id:
        await params.result_callback({"error": "The screen participant is not connected yet."})
        return
    await _request_image(
        params,
        user_id=user_id,
        question=question,
        video_source="screenVideo",
    )


@dataclass(slots=True)
class ServiceBundle:
    llm: Any
    stt: Any | None = None
    tts: Any | None = None


class MediaDiagnosticsObserver(BaseObserver):
    """Count real media frames at the transport boundary."""

    def __init__(self, transport_input: Any, transport_output: Any):
        super().__init__()
        self._transport_input = transport_input
        self._transport_output = transport_output
        self._sender: Callable[[dict[str, Any]], Awaitable[None]] | None = None
        self._counts = {
            "audio_in_frames": 0,
            "camera_frames": 0,
            "screen_frames": 0,
            "text_in_frames": 0,
            "audio_out_frames": 0,
            "requested_images": 0,
        }

    async def attach_sender(
        self, sender: Callable[[dict[str, Any]], Awaitable[None]], profile: SessionProfile
    ) -> None:
        self._sender = sender
        await self._publish(profile_name=profile.name)

    async def on_push_frame(self, data: FramePushed):
        publish = False
        if data.source is self._transport_input:
            frame = data.frame
            if isinstance(frame, InputAudioRawFrame):
                publish = self._increment("audio_in_frames", every=250)
            elif isinstance(frame, InputTextRawFrame):
                publish = self._increment("text_in_frames", every=1)
            elif isinstance(frame, InputImageRawFrame):
                source = frame.transport_source or "camera"
                key = "screen_frames" if source == "screenVideo" else "camera_frames"
                publish = self._increment(key, every=5)
                if getattr(frame, "request", None) is not None:
                    publish = self._increment("requested_images", every=1) or publish
        elif data.destination is self._transport_output and isinstance(
            data.frame, OutputAudioRawFrame
        ):
            publish = self._increment("audio_out_frames", every=250)

        if publish:
            await self._publish()

    def _increment(self, key: str, *, every: int) -> bool:
        self._counts[key] += 1
        return self._counts[key] == 1 or self._counts[key] % every == 0

    async def _publish(self, *, profile_name: str | None = None) -> None:
        details = " ".join(f"{key}={value}" for key, value in self._counts.items())
        logger.info("Media diagnostics | {}", details)
        if self._sender:
            payload: dict[str, Any] = {"type": "media-diagnostics", **self._counts}
            if profile_name:
                payload["profile"] = profile_name
            await self._sender(payload)


def _language(value: str) -> Language:
    try:
        return Language(value)
    except ValueError as exc:
        raise ProfileConfigurationError(f"Language '{value}' is not supported by Pipecat.") from exc


def _settings_kwargs(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def build_realtime_service(config: RealtimeModelConfig) -> ServiceBundle:
    if config.provider == "google":
        settings = GeminiLiveLLMService.Settings(
            **_settings_kwargs(
                model=config.model,
                system_instruction=SYSTEM_PROMPT,
                voice=config.voice,
                language=config.language,
            )
        )
        return ServiceBundle(llm=GeminiLiveLLMService(api_key=config.api_key, settings=settings))

    transcription = InputAudioTranscription(
        **_settings_kwargs(
            model=config.transcription_model,
            language=config.language,
        )
    )
    session_properties = SessionProperties(
        audio=AudioConfiguration(
            input=AudioInput(
                transcription=transcription,
                turn_detection=SemanticTurnDetection(),
                noise_reduction=InputAudioNoiseReduction(type="near_field"),
            ),
            output=AudioOutput(voice=config.voice),
        )
    )
    settings = OpenAIRealtimeLLMService.Settings(
        **_settings_kwargs(
            model=config.model,
            system_instruction=SYSTEM_PROMPT,
            session_properties=session_properties,
        )
    )
    return ServiceBundle(
        llm=OpenAIRealtimeLLMService(
            api_key=config.api_key,
            settings=settings,
            video_frame_detail=config.video_frame_detail,
        )
    )


def build_stt_service(config: ServiceModelConfig) -> Any:
    language = _language(config.language)
    if config.provider in {"openai", "openai-compatible"}:
        return OpenAISTTService(
            api_key=config.api_key,
            base_url=config.base_url,
            settings=OpenAISTTService.Settings(
                **_settings_kwargs(model=config.model, language=language)
            ),
        )
    return GoogleSTTService(
        credentials=config.credentials_json,
        credentials_path=config.credentials_path,
        location=config.location,
        settings=GoogleSTTService.Settings(
            **_settings_kwargs(languages=[language], model=config.model)
        ),
    )


def build_vlm_service(config: ServiceModelConfig) -> Any:
    prompt = SYSTEM_PROMPT + CASCADE_VISUAL_INSTRUCTION
    if not config.api_key:
        raise ProfileConfigurationError(f"{config.provider} VLM requires an API key.")
    if config.adapter == "qwen":
        return QwenLLMService(
            api_key=config.api_key,
            base_url=config.base_url or "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            settings=QwenLLMService.Settings(
                **_settings_kwargs(model=config.model, system_instruction=prompt)
            ),
        )
    if config.provider in {"openai", "openai-compatible"}:
        return OpenAILLMService(
            api_key=config.api_key,
            base_url=config.base_url,
            settings=OpenAILLMService.Settings(
                **_settings_kwargs(model=config.model, system_instruction=prompt)
            ),
        )
    return GoogleLLMService(
        api_key=config.api_key,
        settings=GoogleLLMService.Settings(
            **_settings_kwargs(model=config.model, system_instruction=prompt)
        ),
    )


def build_tts_service(config: ServiceModelConfig) -> Any:
    if config.provider in {"openai", "openai-compatible"}:
        return OpenAITTSService(
            api_key=config.api_key,
            base_url=config.base_url,
            settings=OpenAITTSService.Settings(
                **_settings_kwargs(
                    model=config.model,
                    voice=config.voice,
                )
            ),
        )
    return GoogleTTSService(
        credentials=config.credentials_json,
        credentials_path=config.credentials_path,
        location=config.location,
        settings=GoogleTTSService.Settings(
            **_settings_kwargs(
                model=config.model,
                language=config.language,
                voice=config.voice,
            )
        ),
    )


def build_cascade_services(config: AIModelConfig) -> ServiceBundle:
    if not config.stt or not config.vlm or not config.tts:
        raise ProfileConfigurationError("Cascade mode requires STT, VLM, and TTS configuration.")
    return ServiceBundle(
        stt=build_stt_service(config.stt),
        llm=build_vlm_service(config.vlm),
        tts=build_tts_service(config.tts),
    )


async def run_bot(
    transport: BaseTransport,
    runner_args: RunnerArguments,
    profile: SessionProfile,
    model_config: AIModelConfig,
) -> None:
    logger.info("Starting session | profile={} session_id={}", profile.name, runner_args.session_id)
    if profile.mode == "realtime":
        if not model_config.realtime:
            raise ProfileConfigurationError("Realtime mode requires realtime model configuration.")
        services = build_realtime_service(model_config.realtime)
    else:
        services = build_cascade_services(model_config)

    context = (
        LLMContext(tools=[fetch_camera_image, fetch_screen_image])
        if profile.mode == "cascade"
        else LLMContext()
    )
    use_local_vad = profile.mode == "cascade" or profile == SessionProfile("realtime", "google")
    user_params = (
        LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()) if use_local_vad else None
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=user_params,
    )

    transport_input = transport.input()
    transport_output = transport.output()
    processors = assemble_pipeline_processors(
        profile,
        transport_input=transport_input,
        stt=services.stt,
        user_aggregator=user_aggregator,
        llm=services.llm,
        tts=services.tts,
        transport_output=transport_output,
        assistant_aggregator=assistant_aggregator,
    )
    pipeline = Pipeline(list(processors))
    diagnostics = MediaDiagnosticsObserver(transport_input, transport_output)
    session_resources = SessionResources()
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
        observers=[diagnostics],
        app_resources=session_resources,
    )

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        await rtvi.send_server_message(
            {
                "type": "session-profile",
                "profile": profile.name,
                "pipeline": list(profile.pipeline_steps),
                "models": model_config.public_summary(),
            }
        )
        await diagnostics.attach_sender(rtvi.send_server_message, profile)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        client_id = get_transport_client_id(transport, client)
        session_resources.user_id = client_id
        logger.info("Client connected | profile={} client_id={}", profile.name, client_id)
        await maybe_capture_participant_camera(transport, client, framerate=1)
        await maybe_capture_participant_screen(transport, client, framerate=1)
        logger.info("Video capture started | camera=1fps screen=1fps")

        context.add_message(
            {
                "role": "developer",
                "content": "Briefly introduce yourself and ask how you can help.",
            }
        )
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        session_resources.user_id = None
        logger.info("Client disconnected | profile={}", profile.name)
        await worker.cancel()

    @user_aggregator.event_handler("on_user_turn_stopped")
    async def on_user_turn_stopped(aggregator, strategy, message: UserTurnStoppedMessage):
        logger.info("Transcript | role=user content={}", message.content)

    @assistant_aggregator.event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn_stopped(aggregator, message: AssistantTurnStoppedMessage):
        logger.info("Transcript | role=assistant content={}", message.content)

    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)
    await runner.run()


async def run_configuration_error(
    transport: BaseTransport,
    runner_args: RunnerArguments,
    profile: SessionProfile,
    message: str,
) -> None:
    """Keep the transport alive long enough to report a per-call configuration error."""
    logger.error("Configuration rejected | profile={} error={}", profile.name, message)
    pipeline = Pipeline([transport.input(), transport.output()])
    worker = PipelineWorker(
        pipeline,
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        await rtvi.send_server_message(
            {
                "type": "configuration-error",
                "profile": profile.name,
                "message": message,
            }
        )

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)
    await runner.run()


async def bot(runner_args: RunnerArguments):
    """Pipecat runner entry point; mode/provider are selected per session."""
    default_mode = os.getenv("AI_MODE", "realtime").strip().lower()
    provider_variable = (
        "REALTIME_PROVIDER" if default_mode == "realtime" else "CASCADE_VLM_PROVIDER"
    )
    default_provider = os.getenv(provider_variable) or os.getenv("AI_PROVIDER", "google")
    profile = parse_session_profile(
        runner_args.body,
        default_mode=default_mode,
        default_provider=default_provider,
    )
    logger.info(
        "Requested pipeline | profile={} session_id={}", profile.name, runner_args.session_id
    )
    transport_params = {
        "eval": lambda: EvalTransportParams(audio_in_enabled=True, audio_out_enabled=True),
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            video_in_enabled=True,
        ),
    }
    try:
        model_config = load_model_config(profile.mode, profile.provider, os.environ)
    except ModelConfigurationError as exc:
        transport = await create_transport(runner_args, transport_params)
        await run_configuration_error(transport, runner_args, profile, str(exc))
        return

    logger.info("Selected pipeline | profile={} steps={}", profile.name, profile.pipeline_steps)
    logger.info("Selected models | {}", model_config.public_summary())
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args, profile, model_config)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
