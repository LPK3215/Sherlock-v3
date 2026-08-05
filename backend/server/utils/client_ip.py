"""Resolve request addresses without trusting spoofable proxy headers by default."""

from __future__ import annotations

import os

from fastapi import Request


def _trust_proxy_headers() -> bool:
    return (os.getenv("YUXI_TRUST_PROXY_HEADERS") or "").strip().lower() in {"1", "true", "yes", "on"}


def extract_client_ip(request: Request) -> str:
    if _trust_proxy_headers():
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
