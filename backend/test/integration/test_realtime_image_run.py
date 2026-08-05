"""实时显式附图后端 API 集成测试。

验证：
1. 非视觉模型收到 image_content 时返回 422 而非静默丢图
2. 带 image_content 和 image_meta 的 Run 创建后，Message 保存了图片元数据（需要视觉模型 Agent）
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
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


def _postgres_dsn() -> str:
    return os.getenv("POSTGRES_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/yuxi").replace(
        "+asyncpg", ""
    )


async def _create_token() -> str:
    conn = await asyncpg.connect(_postgres_dsn())
    try:
        user_id = await conn.fetchval(
            "SELECT id FROM users WHERE role = 'superadmin' AND is_deleted = 0 "
            "AND department_id IS NOT NULL ORDER BY id LIMIT 1"
        )
    finally:
        await conn.close()
    assert user_id is not None, "No active superadmin found"
    return AuthUtils.create_access_token({"sub": str(user_id)}, expires_delta=timedelta(minutes=30))


TINY_JPEG_BASE64 = base64.b64encode(
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08"
    b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
    b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
    b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x0f\xff\xc4\x00\x14\x01\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x00\x01\x00\x00?\xff\xd9"
).decode("ascii")


@pytest_asyncio.fixture(scope="function")
async def token() -> str:
    return await _create_token()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_non_vision_model_rejects_image_with_422(token: str):
    """验证非视觉模型收到 image_content 时返回 422 而非静默丢图。"""
    async with httpx.AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        resp = await client.get("/api/agent/default", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, resp.text
        agent = resp.json().get("agent", {})
        slug = agent.get("slug")
        assert slug, "Default agent not found"

        thread_resp = await client.post(
            "/api/chat/thread",
            json={"agent_id": slug, "title": "realtime-non-vision-test", "metadata": {"source": "test"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        thread_id = thread_resp.json().get("thread_id") or thread_resp.json().get("id")

        run_resp = await client.post(
            "/api/agent/runs",
            json={
                "query": "看这张图",
                "agent_slug": slug,
                "thread_id": thread_id,
                "image_content": TINY_JPEG_BASE64,
                "meta": {"source": "realtime", "realtime_session_id": f"test-realtime-{thread_id}"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        if run_resp.status_code == 200:
            run_id = run_resp.json()["run_id"]
            await client.post(f"/api/agent/runs/{run_id}/cancel", json={}, headers={"Authorization": f"Bearer {token}"})
            pytest.skip(f"Agent '{slug}' model supports images — default agent is vision-capable")

        assert run_resp.status_code == 422, (
            f"Expected 422 for non-vision model, got {run_resp.status_code}: {run_resp.text}"
        )
        detail = run_resp.text
        assert "不支持图片" in detail or "image" in detail.lower(), f"Unexpected 422 detail: {detail}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_run_preserves_metadata_or_rejects(token: str):
    """验证带 image_meta 的 Run：视觉模型保存元数据，非视觉模型返回 422。"""
    image_meta = {
        "source": "camera",
        "captured_at": "2026-08-03T10:00:00+00:00",
        "width": 1280,
        "height": 720,
        "mime_type": "image/jpeg",
    }

    async with httpx.AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        resp = await client.get("/api/agent", headers={"Authorization": f"Bearer {token}"})
        agents = resp.json().get("agents") or []
        assert agents, "No agents available"

        for agent in agents:
            slug = agent.get("slug")
            if not slug:
                continue

            thread_resp = await client.post(
                "/api/chat/thread",
                json={"agent_id": slug, "title": "realtime-image-meta-test", "metadata": {"source": "realtime"}},
                headers={"Authorization": f"Bearer {token}"},
            )
            thread_id = thread_resp.json().get("thread_id") or thread_resp.json().get("id")

            run_resp = await client.post(
                "/api/agent/runs",
                json={
                    "query": "看这张图",
                    "agent_slug": slug,
                    "thread_id": thread_id,
                    "image_content": TINY_JPEG_BASE64,
                    "meta": {
                        "source": "realtime",
                        "realtime_session_id": f"test-realtime-{thread_id}",
                        "image_meta": image_meta,
                    },
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            if run_resp.status_code == 422:
                # This agent's model doesn't support images — correct behavior
                continue

            assert run_resp.status_code == 200, f"Run creation failed: {run_resp.status_code} {run_resp.text}"
            run_id = run_resp.json()["run_id"]

            await asyncio.sleep(2)

            conn = await asyncpg.connect(_postgres_dsn())
            try:
                row = await conn.fetchrow(
                    "SELECT message_type, image_content IS NOT NULL as has_image, extra_metadata "
                    "FROM messages WHERE conversation_id IN "
                    "(SELECT id FROM conversations WHERE thread_id = $1) AND role = 'user' "
                    "ORDER BY id DESC LIMIT 1",
                    thread_id,
                )
            finally:
                await conn.close()

            assert row is not None, "No user message found after run creation"
            assert row["message_type"] == "multimodal_image", f"Expected multimodal_image, got {row['message_type']}"
            assert row["has_image"], "image_content should be stored"
            metadata = row["extra_metadata"]
            assert metadata is not None, "extra_metadata should not be null"
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            assert "image_meta" in metadata, f"image_meta not found in extra_metadata: {list(metadata.keys())}"
            assert metadata["image_meta"]["source"] == "camera"
            assert metadata["image_meta"]["width"] == 1280

            await client.post(f"/api/agent/runs/{run_id}/cancel", json={}, headers={"Authorization": f"Bearer {token}"})
            return

        pytest.skip("No vision-capable agent found — all agents returned 422 for image input (correct behavior)")
