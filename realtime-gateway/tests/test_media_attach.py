"""Gateway 媒体附图、抓帧和原子提交单元测试。"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pipecat.frames.frames import LLMContextFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection

from yuxi_client import YuxiRunEvent
from yuxi_llm import YuxiLLMService, YuxiResumeFrame


class FakeFrameBroker:
    """模拟 FrameBroker，返回预设的抓帧结果。"""

    def __init__(self, payload: dict[str, Any] | None = None, error: Exception | None = None):
        self._payload = payload
        self._error = error
        self.captured_sources: list[str] = []

    async def capture(self, source: str, wait_fresh_ms: int) -> dict[str, Any]:
        self.captured_sources.append(source)
        if self._error:
            raise self._error
        return self._payload


def _frame_payload(source: str = "camera") -> dict[str, Any]:
    return {
        "session_id": "rt-1",
        "source": source,
        "mime_type": "image/jpeg",
        "width": 1280,
        "height": 720,
        "captured_at": "2026-08-03T10:00:00+00:00",
        "data_base64": "aW1hZ2U=",
    }


class FakeClient:
    """记录 run_turn 调用参数的假 YuxiAgentClient。"""

    def __init__(self) -> None:
        self.run_turn_calls: list[dict[str, Any]] = []

    async def run_turn(
        self,
        query: str | None,
        *,
        image_content: str | None = None,
        image_meta: dict[str, Any] | None = None,
        resume: Any | None = None,
    ):
        self.run_turn_calls.append({
            "query": query,
            "image_content": image_content,
            "image_meta": image_meta,
            "resume": resume,
        })
        yield YuxiRunEvent(
            event="run.created",
            data={"run_id": "run-1", "thread_id": "thread-1", "status": "pending"},
        )
        yield YuxiRunEvent(
            event="end",
            data={"run_id": "run-1", "thread_id": "thread-1", "payload": {"status": "completed"}},
        )

    async def cancel_active_run(self) -> None:
        pass


def _make_service(client: FakeClient | None = None) -> YuxiLLMService:
    client = client or FakeClient()
    service = YuxiLLMService(client)
    service.push_frame = AsyncMock()
    service.start_processing_metrics = AsyncMock()
    service.stop_processing_metrics = AsyncMock()
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()
    service.push_error = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_media_attach_sets_source():
    service = _make_service()
    service._media_source = "camera"
    assert service._media_source == "camera"


@pytest.mark.asyncio
async def test_text_with_media_captures_frame_and_submits_atomically():
    client = FakeClient()
    service = _make_service(client)
    broker = FakeFrameBroker(payload=_frame_payload("camera"))
    service._frame_broker = broker
    service._media_source = "camera"

    context = LLMContext(messages=[{"role": "user", "content": "看画面"}])
    await service.process_frame(LLMContextFrame(context), FrameDirection.DOWNSTREAM)

    assert broker.captured_sources == ["camera"]
    assert len(client.run_turn_calls) == 1
    call = client.run_turn_calls[0]
    assert call["query"] == "看画面"
    assert call["image_content"] == "aW1hZ2U="
    assert call["image_meta"]["source"] == "camera"
    assert call["image_meta"]["width"] == 1280
    assert call["image_meta"]["mime_type"] == "image/jpeg"
    assert service._media_source is None


@pytest.mark.asyncio
async def test_text_without_media_does_not_capture_frame():
    client = FakeClient()
    service = _make_service(client)
    broker = FakeFrameBroker(payload=_frame_payload())
    service._frame_broker = broker
    service._media_source = None

    context = LLMContext(messages=[{"role": "user", "content": "hello"}])
    await service.process_frame(LLMContextFrame(context), FrameDirection.DOWNSTREAM)

    assert broker.captured_sources == []
    assert len(client.run_turn_calls) == 1
    assert client.run_turn_calls[0]["image_content"] is None
    assert client.run_turn_calls[0]["image_meta"] is None


@pytest.mark.asyncio
async def test_resume_does_not_consume_media_selection():
    client = FakeClient()
    service = _make_service(client)
    broker = FakeFrameBroker(payload=_frame_payload())
    service._frame_broker = broker
    service._media_source = "screen"

    await service.process_frame(YuxiResumeFrame(answer={"choice": "a"}), FrameDirection.DOWNSTREAM)

    assert broker.captured_sources == []
    assert len(client.run_turn_calls) == 1
    assert client.run_turn_calls[0]["image_content"] is None
    assert client.run_turn_calls[0]["resume"] == {"choice": "a"}
    assert service._media_source == "screen"


@pytest.mark.asyncio
async def test_frame_timeout_pushes_error_and_keeps_media_source():
    client = FakeClient()
    service = _make_service(client)
    broker = FakeFrameBroker(error=TimeoutError())
    service._frame_broker = broker
    service._media_source = "camera"

    context = LLMContext(messages=[{"role": "user", "content": "看画面"}])
    await service.process_frame(LLMContextFrame(context), FrameDirection.DOWNSTREAM)

    service.push_error.assert_awaited()
    assert service._media_source == "camera"


@pytest.mark.asyncio
async def test_frame_broker_runtime_error_pushes_error():
    client = FakeClient()
    service = _make_service(client)
    broker = FakeFrameBroker(error=RuntimeError("realtime media client is not connected"))
    service._frame_broker = broker
    service._media_source = "camera"

    context = LLMContext(messages=[{"role": "user", "content": "看画面"}])
    await service.process_frame(LLMContextFrame(context), FrameDirection.DOWNSTREAM)

    service.push_error.assert_awaited()


@pytest.mark.asyncio
async def test_run_creation_failure_keeps_media_source():
    class FailingClient(FakeClient):
        async def run_turn(self, query, *, image_content=None, image_meta=None, resume=None):
            self.run_turn_calls.append({
                "query": query,
                "image_content": image_content,
                "image_meta": image_meta,
                "resume": resume,
            })
            from yuxi_client import YuxiAPIError
            raise YuxiAPIError("创建 Yuxi Agent Run 失败 (422): 模型不支持图片")
            yield  # noqa: unreachable — makes this an async generator

    client = FailingClient()
    service = _make_service(client)
    broker = FakeFrameBroker(payload=_frame_payload("camera"))
    service._frame_broker = broker
    service._media_source = "camera"

    context = LLMContext(messages=[{"role": "user", "content": "看画面"}])
    await service.process_frame(LLMContextFrame(context), FrameDirection.DOWNSTREAM)

    service.push_error.assert_awaited()
    assert service._media_source == "camera"


@pytest.mark.asyncio
async def test_screen_capture_uses_screen_source():
    client = FakeClient()
    service = _make_service(client)
    broker = FakeFrameBroker(payload=_frame_payload("screen"))
    service._frame_broker = broker
    service._media_source = "screen"

    context = LLMContext(messages=[{"role": "user", "content": "看屏幕"}])
    await service.process_frame(LLMContextFrame(context), FrameDirection.DOWNSTREAM)

    assert broker.captured_sources == ["screen"]
    assert client.run_turn_calls[0]["image_meta"]["source"] == "screen"
    assert service._media_source is None
