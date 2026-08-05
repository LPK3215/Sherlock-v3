"""Shared helpers for toolkit runtime context."""

from __future__ import annotations


def get_runtime_uid(runtime) -> str:
    """Return the authenticated user UID carried by a tool runtime."""
    uid = str(getattr(getattr(runtime, "context", None), "uid", "") or "").strip()
    if not uid:
        raise ValueError("当前运行缺少用户身份")
    return uid
