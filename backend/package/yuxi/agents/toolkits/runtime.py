"""Shared helpers for toolkit runtime context."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_CURRENT_TOOL_RUNTIME: ContextVar[Any | None] = ContextVar("current_tool_runtime", default=None)


def set_current_tool_runtime(runtime: Any | None):
    """Store the current tool runtime for tools that receive it indirectly."""
    return _CURRENT_TOOL_RUNTIME.set(runtime)


def reset_current_tool_runtime(token) -> None:
    """Restore the previous tool runtime after a tool call finishes."""
    _CURRENT_TOOL_RUNTIME.reset(token)


def get_current_tool_runtime() -> Any | None:
    """Return the active tool runtime if one is available."""
    return _CURRENT_TOOL_RUNTIME.get()


def get_runtime_uid(runtime: Any | None = None) -> str:
    """Return the authenticated user UID carried by a tool runtime."""
    runtime = runtime or get_current_tool_runtime()
    uid = str(getattr(getattr(runtime, "context", None), "uid", "") or "").strip()
    if not uid:
        raise ValueError("当前运行缺少用户身份")
    return uid
