"""Pipecat LLM adapter backed by the standard Yuxi AgentRun lifecycle."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from pipecat.frames.frames import (
    DataFrame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame
from pipecat.services.llm_service import LLMService

from yuxi_client import (
    YuxiAgentClient,
    YuxiAPIError,
    event_text_deltas,
    normalized_event,
)


@dataclass
class YuxiResumeFrame(DataFrame):
    answer: Any


class YuxiLLMService(LLMService):
    def __init__(self, client: YuxiAgentClient) -> None:
        super().__init__(name="LLM(Yuxi AgentRun)")
        self._client = client
        self._run_lock = asyncio.Lock()

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, YuxiResumeFrame):
            await self._run_agent(query=None, resume=frame.answer)
            return

        if not isinstance(frame, LLMContextFrame):
            await self.push_frame(frame, direction)
            return

        query, image_content = self._latest_user_input(frame.context)
        await self._run_agent(query=query, image_content=image_content)

    async def _run_agent(
        self,
        *,
        query: str | None,
        image_content: str | None = None,
        resume: Any | None = None,
    ) -> None:
        async with self._run_lock:
            await self.push_frame(LLMFullResponseStartFrame())
            await self.start_processing_metrics()
            try:
                await self.start_ttfb_metrics()
                first_delta = True
                async for event in self._client.run_turn(
                    query,
                    image_content=image_content,
                    resume=resume,
                ):
                    await self._push_agent_event(event)
                    for delta in event_text_deltas(event):
                        if first_delta:
                            await self.stop_ttfb_metrics()
                            first_delta = False
                        await self._push_llm_text(delta)
            except asyncio.CancelledError:
                await self._client.cancel_active_run()
                raise
            except YuxiAPIError as exc:
                await self.push_error(error_msg=str(exc), exception=exc)
            except Exception as exc:
                await self.push_error(error_msg=f"Yuxi Agent Run failed: {exc}", exception=exc)
            finally:
                await self.stop_processing_metrics()
                await self.push_frame(LLMFullResponseEndFrame())

    async def _push_agent_event(self, event) -> None:
        await self.push_frame(yuxi_agent_event_frame(event))

    @staticmethod
    def _latest_user_input(context: LLMContext) -> tuple[str, str | None]:
        for message in reversed(context.get_messages()):
            if message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip(), None
            if isinstance(content, list):
                text_parts: list[str] = []
                image_content: str | None = None
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "text" and isinstance(part.get("text"), str):
                        text_parts.append(part["text"])
                    if part.get("type") == "image_url":
                        image_content = _data_url_content(part.get("image_url")) or image_content
                query = "\n".join(segment for segment in text_parts if segment).strip()
                if query or image_content:
                    return query, image_content
        raise YuxiAPIError("没有可提交给 Yuxi 的用户消息")


def _data_url_content(image_url: Any) -> str | None:
    if isinstance(image_url, dict):
        image_url = image_url.get("url")
    if not isinstance(image_url, str):
        return None
    marker = ";base64,"
    if image_url.startswith("data:image/") and marker in image_url:
        return image_url.split(marker, 1)[1]
    return None


def yuxi_agent_event_frame(event) -> RTVIServerMessageFrame:
    return RTVIServerMessageFrame(
        data={"type": "yuxi-agent-event", "payload": normalized_event(event)}
    )
