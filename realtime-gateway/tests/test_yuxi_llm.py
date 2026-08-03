from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import LLMContextFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from yuxi_client import YuxiRunEvent
from yuxi_llm import YuxiLLMService, YuxiResumeFrame


def test_latest_user_input_ignores_local_assistant_history():
    context = LLMContext(
        messages=[
            {"role": "assistant", "content": "旧回答"},
            {"role": "user", "content": "新的问题"},
        ]
    )

    assert YuxiLLMService._latest_user_input(context) == ("新的问题", None)


def test_latest_user_input_extracts_base64_image():
    context = LLMContext(
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "看一下画面"},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,aW1hZ2U="}},
                ],
            }
        ]
    )

    assert YuxiLLMService._latest_user_input(context) == ("看一下画面", "aW1hZ2U=")


@pytest.mark.asyncio
async def test_agent_events_use_rtvi_server_message_frame():
    class FakeClient:
        async def run_turn(
            self,
            query: str,
            *,
            image_content: str | None = None,
            resume=None,
        ):
            assert query == "新的问题"
            assert image_content is None
            assert resume is None
            yield YuxiRunEvent(
                event="run.created",
                data={"run_id": "run-1", "thread_id": "thread-1", "status": "pending"},
            )

    service = YuxiLLMService(FakeClient())
    service.push_frame = AsyncMock()
    service.start_processing_metrics = AsyncMock()
    service.stop_processing_metrics = AsyncMock()
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()

    await service.process_frame(
        LLMContextFrame(LLMContext(messages=[{"role": "user", "content": "新的问题"}])),
        FrameDirection.DOWNSTREAM,
    )

    event_frame = next(
        call.args[0]
        for call in service.push_frame.await_args_list
        if isinstance(call.args[0], RTVIServerMessageFrame)
    )
    assert event_frame.data == {
        "type": "yuxi-agent-event",
        "payload": {
            "type": "run.started",
            "seq": None,
            "run_id": "run-1",
            "thread_id": "thread-1",
            "status": "pending",
            "detail": {
                "run_id": "run-1",
                "thread_id": "thread-1",
                "status": "pending",
            },
        },
    }


@pytest.mark.asyncio
async def test_resume_frame_uses_structured_answer():
    answer = {"choice": "a"}

    class FakeClient:
        async def run_turn(
            self,
            query: str | None,
            *,
            image_content: str | None = None,
            resume=None,
        ):
            assert query is None
            assert image_content is None
            assert resume == answer
            yield YuxiRunEvent(
                event="run.created",
                data={"run_id": "run-resume", "thread_id": "thread-1", "status": "pending"},
            )

    service = YuxiLLMService(FakeClient())
    service.push_frame = AsyncMock()
    service.start_processing_metrics = AsyncMock()
    service.stop_processing_metrics = AsyncMock()
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()

    await service.process_frame(YuxiResumeFrame(answer=answer), FrameDirection.DOWNSTREAM)

    event_frame = next(
        call.args[0]
        for call in service.push_frame.await_args_list
        if isinstance(call.args[0], RTVIServerMessageFrame)
    )
    assert event_frame.data["payload"]["run_id"] == "run-resume"
