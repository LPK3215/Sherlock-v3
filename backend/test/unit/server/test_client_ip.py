from __future__ import annotations

from types import SimpleNamespace

from server.utils.client_ip import extract_client_ip


def _request(headers=None, host="10.0.0.5"):
    return SimpleNamespace(headers=headers or {}, client=SimpleNamespace(host=host))


def test_forwarded_headers_are_not_trusted_by_default(monkeypatch):
    monkeypatch.delenv("SHERLOCK_TRUST_PROXY_HEADERS", raising=False)

    assert extract_client_ip(_request({"x-forwarded-for": "203.0.113.8"})) == "10.0.0.5"


def test_forwarded_headers_are_used_when_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("SHERLOCK_TRUST_PROXY_HEADERS", "true")

    assert extract_client_ip(_request({"x-forwarded-for": "203.0.113.8, 10.0.0.5"})) == "203.0.113.8"
