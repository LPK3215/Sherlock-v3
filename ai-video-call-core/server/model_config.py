"""Unified model configuration for realtime and cascade sessions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, cast

Provider = Literal["google", "openai", "openai-compatible"]
Component = Literal["stt", "vlm", "tts"]
VLMAdapter = Literal["google", "openai", "qwen"]

VALID_PROVIDERS = frozenset({"google", "openai", "openai-compatible"})
REALTIME_PROVIDERS = frozenset({"google", "openai"})


class ModelConfigurationError(ValueError):
    """Raised when a model service cannot be built from configuration."""


@dataclass(frozen=True, slots=True)
class RealtimeModelConfig:
    provider: Provider
    model: str | None
    voice: str
    language: str
    api_key: str = field(repr=False)
    transcription_model: str | None = None
    video_frame_detail: str = "auto"

    def public_summary(self) -> dict[str, str | None]:
        return {"provider": self.provider, "model": self.model, "voice": self.voice}


@dataclass(frozen=True, slots=True)
class ServiceModelConfig:
    component: Component
    provider: Provider
    model: str | None
    adapter: VLMAdapter | None = None
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None
    voice: str | None = None
    language: str = "zh-CN"
    location: str = "global"
    credentials_json: str | None = field(default=None, repr=False)
    credentials_path: str | None = field(default=None, repr=False)

    def public_summary(self) -> dict[str, str | None]:
        return {
            "provider": self.provider,
            "model": self.model,
            "adapter": self.adapter,
            "endpoint": self.base_url,
            "voice": self.voice,
        }


@dataclass(frozen=True, slots=True)
class AIModelConfig:
    mode: Literal["realtime", "cascade"]
    realtime: RealtimeModelConfig | None = None
    stt: ServiceModelConfig | None = None
    vlm: ServiceModelConfig | None = None
    tts: ServiceModelConfig | None = None

    def public_summary(self) -> dict[str, Any]:
        if self.realtime:
            return {"realtime": self.realtime.public_summary()}
        return {
            "stt": self.stt.public_summary() if self.stt else None,
            "vlm": self.vlm.public_summary() if self.vlm else None,
            "tts": self.tts.public_summary() if self.tts else None,
        }


def normalize_provider(value: str) -> Provider:
    provider = value.strip().lower().replace("_", "-")
    if provider not in VALID_PROVIDERS:
        choices = ", ".join(sorted(VALID_PROVIDERS))
        raise ModelConfigurationError(
            f"Unsupported model provider '{value}'. Choose one of: {choices}."
        )
    return cast(Provider, provider)


def _first(env: Mapping[str, str], *names: str, default: str | None = None) -> str | None:
    for name in names:
        value = env.get(name, "").strip()
        if value:
            return value
    return default


def _required(value: str | None, name: str) -> str:
    if value:
        return value
    raise ModelConfigurationError(f"Missing required model configuration: {name}.")


def _load_realtime(provider: Provider, env: Mapping[str, str]) -> RealtimeModelConfig:
    language = _first(env, "AI_LANGUAGE", default="zh-CN") or "zh-CN"
    if provider == "google":
        return RealtimeModelConfig(
            provider=provider,
            api_key=_required(
                _first(env, "REALTIME_GOOGLE_API_KEY", "GOOGLE_API_KEY"),
                "REALTIME_GOOGLE_API_KEY or GOOGLE_API_KEY",
            ),
            model=_first(env, "REALTIME_GOOGLE_MODEL", "GEMINI_LIVE_MODEL"),
            voice=_first(env, "REALTIME_GOOGLE_VOICE", "GEMINI_LIVE_VOICE", default="Charon")
            or "Charon",
            language=language,
        )
    if provider == "openai":
        return RealtimeModelConfig(
            provider=provider,
            api_key=_required(
                _first(env, "REALTIME_OPENAI_API_KEY", "OPENAI_API_KEY"),
                "REALTIME_OPENAI_API_KEY or OPENAI_API_KEY",
            ),
            model=_first(env, "REALTIME_OPENAI_MODEL", "OPENAI_REALTIME_MODEL"),
            voice=_first(env, "REALTIME_OPENAI_VOICE", "OPENAI_REALTIME_VOICE", default="alloy")
            or "alloy",
            language=language,
            transcription_model=_first(
                env,
                "REALTIME_OPENAI_TRANSCRIPTION_MODEL",
                "OPENAI_REALTIME_TRANSCRIPTION_MODEL",
            ),
            video_frame_detail=_first(
                env,
                "REALTIME_OPENAI_VIDEO_FRAME_DETAIL",
                "OPENAI_VIDEO_FRAME_DETAIL",
                default="auto",
            )
            or "auto",
        )
    raise ModelConfigurationError(
        "Realtime mode requires a native realtime provider: google or openai."
    )


def _legacy_model_name(component: Component, provider: Provider) -> str | None:
    names = {
        ("stt", "google"): "GOOGLE_STT_MODEL",
        ("stt", "openai"): "OPENAI_STT_MODEL",
        ("vlm", "google"): "GOOGLE_LLM_MODEL",
        ("vlm", "openai"): "OPENAI_LLM_MODEL",
        ("tts", "google"): "GOOGLE_TTS_MODEL",
        ("tts", "openai"): "OPENAI_TTS_MODEL",
    }
    return names.get((component, provider))


def _load_cascade_component(
    component: Component,
    provider: Provider,
    env: Mapping[str, str],
) -> ServiceModelConfig:
    prefix = f"CASCADE_{component.upper()}"
    language_names = [f"{prefix}_LANGUAGE"]
    if component == "tts" and provider == "google":
        language_names.append("GOOGLE_TTS_LANGUAGE")
    language_names.append("AI_LANGUAGE")
    language = _first(env, *language_names, default="zh-CN") or "zh-CN"
    location = _first(env, f"{prefix}_LOCATION", "GOOGLE_CLOUD_LOCATION", default="global")
    legacy_model = _legacy_model_name(component, provider)
    model_names = (
        [f"{prefix}_MODEL"]
        if provider == "openai-compatible"
        else [f"{prefix}_{provider.upper()}_MODEL"]
    )
    if legacy_model and provider != "openai-compatible":
        model_names.append(legacy_model)
    model_default = "latest_long" if component == "stt" and provider == "google" else None
    model = _first(env, *model_names, default=model_default)
    adapter: VLMAdapter | None = None
    if component == "vlm":
        if provider == "google":
            adapter = "google"
        elif provider == "openai":
            adapter = "openai"
        else:
            configured_adapter = _first(env, "CASCADE_VLM_ADAPTER")
            inferred_adapter = "qwen" if model and "qwen" in model.lower() else "openai"
            adapter_value = (configured_adapter or inferred_adapter).strip().lower()
            if adapter_value not in {"openai", "qwen"}:
                raise ModelConfigurationError("CASCADE_VLM_ADAPTER must be 'openai' or 'qwen'.")
            adapter = cast(VLMAdapter, adapter_value)
    voice = None
    if component == "tts":
        legacy_voice = "GOOGLE_TTS_VOICE" if provider == "google" else "OPENAI_TTS_VOICE"
        voice_default = "cmn-CN-Chirp3-HD-Charon" if provider == "google" else "alloy"
        voice_names = (
            [f"{prefix}_VOICE"]
            if provider == "openai-compatible"
            else [f"{prefix}_{provider.upper()}_VOICE", legacy_voice]
        )
        voice = _first(env, *voice_names, default=voice_default)

    if provider == "google":
        if component == "vlm":
            api_key = _required(
                _first(env, f"{prefix}_GOOGLE_API_KEY", "GOOGLE_API_KEY"),
                f"{prefix}_GOOGLE_API_KEY or GOOGLE_API_KEY",
            )
            return ServiceModelConfig(
                component=component,
                provider=provider,
                api_key=api_key,
                model=model,
                adapter=adapter,
                language=language,
            )

        credentials_json = _first(env, f"{prefix}_CREDENTIALS_JSON", "GOOGLE_CREDENTIALS_JSON")
        credentials_path = _first(
            env, f"{prefix}_CREDENTIALS_PATH", "GOOGLE_APPLICATION_CREDENTIALS"
        )
        if not credentials_json and not credentials_path:
            raise ModelConfigurationError(
                f"Missing required model configuration for {component}: "
                f"{prefix}_CREDENTIALS_JSON or {prefix}_CREDENTIALS_PATH "
                "(legacy GOOGLE_CREDENTIALS_JSON or GOOGLE_APPLICATION_CREDENTIALS also works)."
            )
        return ServiceModelConfig(
            component=component,
            provider=provider,
            model=model,
            adapter=adapter,
            voice=voice,
            language=language,
            location=location or "global",
            credentials_json=credentials_json,
            credentials_path=credentials_path,
        )

    if provider == "openai":
        api_key = _required(
            _first(env, f"{prefix}_OPENAI_API_KEY", "OPENAI_API_KEY"),
            f"{prefix}_OPENAI_API_KEY or OPENAI_API_KEY",
        )
        return ServiceModelConfig(
            component=component,
            provider=provider,
            api_key=api_key,
            model=model,
            adapter=adapter,
            voice=voice,
            language=language,
        )

    api_key = _required(_first(env, f"{prefix}_API_KEY"), f"{prefix}_API_KEY")
    base_url = _required(_first(env, f"{prefix}_BASE_URL"), f"{prefix}_BASE_URL")
    model = _required(model, f"{prefix}_MODEL")
    return ServiceModelConfig(
        component=component,
        provider=provider,
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        model=model,
        adapter=adapter,
        voice=voice,
        language=language,
    )


def load_model_config(
    mode: str,
    primary_provider: str,
    env: Mapping[str, str],
) -> AIModelConfig:
    """Resolve all model services for one session without exposing credentials."""
    provider = normalize_provider(primary_provider)
    if mode == "realtime":
        if provider not in REALTIME_PROVIDERS:
            raise ModelConfigurationError(
                "Realtime mode supports google or openai; OpenAI-compatible chat endpoints "
                "belong in cascade mode."
            )
        return AIModelConfig(mode="realtime", realtime=_load_realtime(provider, env))
    if mode != "cascade":
        raise ModelConfigurationError(f"Unsupported AI mode '{mode}'.")

    native_default = provider if provider in REALTIME_PROVIDERS else "openai"
    stt_provider = normalize_provider(
        _first(env, "CASCADE_STT_PROVIDER", default=native_default) or native_default
    )
    tts_provider = normalize_provider(
        _first(env, "CASCADE_TTS_PROVIDER", default=native_default) or native_default
    )
    return AIModelConfig(
        mode="cascade",
        stt=_load_cascade_component("stt", stt_provider, env),
        vlm=_load_cascade_component("vlm", provider, env),
        tts=_load_cascade_component("tts", tts_provider, env),
    )
