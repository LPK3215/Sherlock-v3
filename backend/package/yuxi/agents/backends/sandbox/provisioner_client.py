from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

CREATE_TIMEOUT_BUFFER_SECONDS = 30


@dataclass(slots=True)
class SandboxRecord:
    sandbox_id: str
    sandbox_url: str
    status: str | None = None


class ProvisionerClient:
    def __init__(
        self,
        base_url: str,
        *,
        token: str,
        timeout_seconds: int = 20,
        create_timeout_seconds: int | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds)
        if create_timeout_seconds is None:
            health_timeout_seconds = int(os.getenv("SANDBOX_HEALTH_TIMEOUT_SECONDS", "300"))
            create_timeout_seconds = health_timeout_seconds + CREATE_TIMEOUT_BUFFER_SECONDS
        self._create_timeout = httpx.Timeout(create_timeout_seconds)
        self._headers = {"Authorization": f"Bearer {token}"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: httpx.Timeout | None = None,
        **kwargs,
    ) -> httpx.Response:
        return httpx.request(
            method=method,
            url=f"{self._base_url}{path}",
            timeout=timeout or self._timeout,
            headers=self._headers,
            **kwargs,
        )

    def health(self) -> bool:
        response = self._request("GET", "/health")
        return response.status_code == 200

    def create(
        self,
        sandbox_id: str,
        thread_id: str,
        uid: str,
        env: dict[str, str] | None = None,
        *,
        file_thread_id: str | None = None,
        skills_thread_id: str | None = None,
    ) -> SandboxRecord:
        response = self._request(
            "POST",
            "/api/sandboxes",
            timeout=self._create_timeout,
            json={
                "sandbox_id": sandbox_id,
                "thread_id": thread_id,
                "file_thread_id": file_thread_id or thread_id,
                "skills_thread_id": skills_thread_id or thread_id,
                "uid": uid,
                "env": env or {},
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"failed to create sandbox {sandbox_id}: {response.status_code} {response.text}")
        payload = response.json()
        return SandboxRecord(
            sandbox_id=payload["sandbox_id"],
            sandbox_url=payload["sandbox_url"],
            status=payload.get("status"),
        )

    def discover(self, sandbox_id: str) -> SandboxRecord | None:
        response = self._request("GET", f"/api/sandboxes/{sandbox_id}")
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise RuntimeError(f"failed to discover sandbox {sandbox_id}: {response.status_code} {response.text}")
        payload = response.json()
        return SandboxRecord(
            sandbox_id=payload["sandbox_id"],
            sandbox_url=payload["sandbox_url"],
            status=payload.get("status"),
        )

    def touch(self, sandbox_id: str) -> bool:
        response = self._request("POST", f"/api/sandboxes/{sandbox_id}/touch")
        if response.status_code == 404:
            return False
        if response.status_code >= 400:
            raise RuntimeError(f"failed to touch sandbox {sandbox_id}: {response.status_code} {response.text}")
        return True

    def delete(self, sandbox_id: str) -> None:
        response = self._request("DELETE", f"/api/sandboxes/{sandbox_id}")
        if response.status_code in {200, 404}:
            return
        raise RuntimeError(f"failed to delete sandbox {sandbox_id}: {response.status_code} {response.text}")
