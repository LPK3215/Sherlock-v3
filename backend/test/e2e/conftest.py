from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator
from datetime import timedelta
from pathlib import Path

import asyncpg
import httpx
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from yuxi.utils.auth_utils import AuthUtils

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(PROJECT_ROOT / "test/.env.test", override=False)

E2E_BASE_URL = os.getenv("TEST_BASE_URL", os.getenv("API_BASE_URL", "http://localhost:5050")).rstrip("/")
E2E_USERNAME = os.getenv("E2E_USERNAME") or os.getenv("TEST_USERNAME")
E2E_PASSWORD = os.getenv("E2E_PASSWORD") or os.getenv("TEST_PASSWORD")
E2E_ACCESS_TOKEN = os.getenv("E2E_ACCESS_TOKEN")
E2E_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


def _postgres_dsn() -> str:
    return os.getenv("POSTGRES_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/yuxi").replace(
        "+asyncpg", ""
    )


async def _create_local_e2e_token() -> str:
    conn = await asyncpg.connect(_postgres_dsn())
    try:
        user_id = await conn.fetchval(
            """
            SELECT id
            FROM users
            WHERE role = 'superadmin' AND is_deleted = 0 AND department_id IS NOT NULL
            ORDER BY id
            LIMIT 1
            """
        )
    finally:
        await conn.close()

    if user_id is None:
        pytest.fail("No active superadmin is available for Docker E2E authentication.")
    return AuthUtils.create_access_token({"sub": str(user_id)}, expires_delta=timedelta(minutes=30))


@pytest.fixture(scope="session")
def e2e_base_url() -> str:
    return E2E_BASE_URL


@pytest_asyncio.fixture(scope="function")
async def e2e_client(e2e_base_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(base_url=e2e_base_url, timeout=E2E_TIMEOUT, follow_redirects=True) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def e2e_headers(e2e_client: httpx.AsyncClient) -> dict[str, str]:
    access_token = E2E_ACCESS_TOKEN
    if not access_token and E2E_USERNAME and E2E_PASSWORD:
        response = await e2e_client.post(
            "/api/auth/token",
            data={"username": E2E_USERNAME, "password": E2E_PASSWORD},
        )
        if response.status_code != 200:
            pytest.fail(f"E2E login failed (status={response.status_code}): {response.text}")
        access_token = response.json().get("access_token")
        if not access_token:
            pytest.fail("E2E login succeeded but no access token was returned.")
    if not access_token:
        access_token = await _create_local_e2e_token()
    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture(scope="function")
async def e2e_agent_context(e2e_client: httpx.AsyncClient, e2e_headers: dict[str, str]) -> dict[str, str]:
    me_response = await e2e_client.get("/api/auth/me", headers=e2e_headers)
    if me_response.status_code != 200:
        pytest.fail(
            f"Failed to fetch current user for E2E tests (status={me_response.status_code}): {me_response.text}"
        )
    uid = me_response.json().get("uid")
    if not uid:
        pytest.fail("Current user payload missing uid field for E2E tests.")

    default_response = await e2e_client.get("/api/agent/default", headers=e2e_headers)
    if default_response.status_code == 200:
        agent = default_response.json().get("agent") or {}
    else:
        response = await e2e_client.get("/api/agent", headers=e2e_headers)
        if response.status_code != 200:
            pytest.fail(f"Failed to list agents for E2E tests (status={response.status_code}): {response.text}")
        agents = response.json().get("agents") or []
        if not agents:
            pytest.fail("No agents are available for E2E tests.")
        agent = agents[0]

    agent_slug = agent.get("slug") or agent.get("agent_id")
    if not agent_slug:
        pytest.fail(f"Agent payload missing slug/agent_id field for E2E tests: {agent}")

    return {"agent_slug": str(agent_slug), "agent_id": str(agent_slug), "uid": str(uid)}
