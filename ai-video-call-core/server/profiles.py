"""Session profile parsing and provider-independent pipeline assembly."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from model_config import (
    ModelConfigurationError,
    Provider,
    load_model_config,
    normalize_provider,
)

Mode = Literal["realtime", "cascade"]

VALID_MODES = frozenset({"realtime", "cascade"})


class ProfileConfigurationError(ValueError):
    """Raised when a requested session profile cannot be configured."""


@dataclass(frozen=True, slots=True)
class SessionProfile:
    mode: Mode
    provider: Provider

    @property
    def name(self) -> str:
        return f"{self.mode}/{self.provider}"

    @property
    def pipeline_steps(self) -> tuple[str, ...]:
        if self.mode == "realtime":
            return ("transport.input", "user", "realtime_llm", "transport.output", "assistant")
        return (
            "transport.input",
            "stt",
            "user",
            "multimodal_llm",
            "tts",
            "transport.output",
            "assistant",
        )


def _nested_mapping(body: Mapping[str, Any]) -> Mapping[str, Any]:
    current = body
    for key in ("requestData", "request_data", "body"):
        nested = current.get(key)
        if isinstance(nested, Mapping) and not ({"mode", "provider"} & current.keys()):
            current = nested
    return current


def parse_session_profile(
    body: Any,
    *,
    default_mode: str = "realtime",
    default_provider: str = "google",
) -> SessionProfile:
    """Parse the per-call profile passed through ``runner_args.body``."""
    data = _nested_mapping(body) if isinstance(body, Mapping) else {}
    mode = str(data.get("mode", default_mode)).strip().lower()
    raw_provider = str(data.get("provider", default_provider))

    if mode not in VALID_MODES:
        choices = ", ".join(sorted(VALID_MODES))
        raise ProfileConfigurationError(f"Unsupported AI mode '{mode}'. Choose one of: {choices}.")
    try:
        provider = normalize_provider(raw_provider)
    except ModelConfigurationError as exc:
        raise ProfileConfigurationError(str(exc).replace("model provider", "AI provider")) from exc
    if mode == "realtime" and provider == "openai-compatible":
        raise ProfileConfigurationError(
            "Realtime mode supports google or openai; use openai-compatible with cascade mode."
        )

    return SessionProfile(mode=mode, provider=provider)  # type: ignore[arg-type]


def validate_profile_environment(profile: SessionProfile, env: Mapping[str, str]) -> None:
    """Validate credentials without reading or exposing their values."""
    try:
        load_model_config(profile.mode, profile.provider, env)
    except ModelConfigurationError as exc:
        raise ProfileConfigurationError(f"Profile {profile.name}: {exc}") from exc


T = TypeVar("T")


def assemble_pipeline_processors(
    profile: SessionProfile,
    *,
    transport_input: T,
    user_aggregator: T,
    llm: T,
    transport_output: T,
    assistant_aggregator: T,
    stt: T | None = None,
    tts: T | None = None,
) -> Sequence[T]:
    """Return processors in Pipecat's canonical order for the selected mode."""
    if profile.mode == "realtime":
        return [
            transport_input,
            user_aggregator,
            llm,
            transport_output,
            assistant_aggregator,
        ]

    if stt is None or tts is None:
        raise ProfileConfigurationError("Cascade mode requires both STT and TTS services.")

    return [
        transport_input,
        stt,
        user_aggregator,
        llm,
        tts,
        transport_output,
        assistant_aggregator,
    ]
