"""STT and TTS factories used by the realtime cascade pipeline."""

from __future__ import annotations

import os
from importlib import import_module
from pathlib import Path

from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.tts import OpenAITTSService

from yuxi.config import config
from yuxi.utils.logging_config import logger


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _required(key: str) -> str:
    value = _env(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _service_class(module_path: str, class_name: str):
    return getattr(import_module(module_path), class_name)


def create_stt_service():
    provider = _env("CASCADE_STT_PROVIDER", "whisper").lower()
    logger.info(f"Realtime STT provider: {provider}")

    if provider == "whisper":
        service_class = _service_class("pipecat.services.whisper.stt", "WhisperSTTService")
        return service_class(
            settings=service_class.Settings(model=_env("CASCADE_STT_WHISPER_MODEL", "tiny")),
            device=_env("CASCADE_STT_WHISPER_DEVICE", "cpu"),
            compute_type=_env("CASCADE_STT_WHISPER_COMPUTE_TYPE", "int8"),
            name="STT(Whisper)",
        )

    if provider == "openai":
        return OpenAISTTService(
            model=_env("CASCADE_STT_OPENAI_MODEL", "whisper-1"),
            api_key=_required("CASCADE_STT_OPENAI_API_KEY"),
            base_url=_env("CASCADE_STT_OPENAI_BASE_URL") or None,
            name="STT(OpenAI)",
        )

    raise RuntimeError(f"Unsupported CASCADE_STT_PROVIDER: {provider}")


def create_tts_service():
    provider = _env("CASCADE_TTS_PROVIDER", "piper").lower()
    logger.info(f"Realtime TTS provider: {provider}")

    if provider == "piper":
        service_class = _service_class("pipecat.services.piper.tts", "PiperTTSService")
        download_dir = Path(config.save_dir) / "models" / "piper"
        download_dir.mkdir(parents=True, exist_ok=True)
        return service_class(
            settings=service_class.Settings(voice=_env("CASCADE_TTS_PIPER_VOICE", "zh_CN-huayan-medium")),
            download_dir=download_dir,
            name="TTS(Piper)",
        )

    if provider == "openai":
        return OpenAITTSService(
            model=_env("CASCADE_TTS_OPENAI_MODEL", "tts-1"),
            api_key=_required("CASCADE_TTS_OPENAI_API_KEY"),
            base_url=_env("CASCADE_TTS_OPENAI_BASE_URL") or None,
            voice=_env("CASCADE_TTS_OPENAI_VOICE", "alloy"),
            name="TTS(OpenAI)",
        )

    raise RuntimeError(f"Unsupported CASCADE_TTS_PROVIDER: {provider}")
