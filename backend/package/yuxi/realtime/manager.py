"""WebRTC session lifecycle owned by the Yuxi backend."""

from __future__ import annotations

import asyncio
import uuid

from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

from yuxi.realtime.pipeline import RealtimeSessionConfig, run_realtime_pipeline
from yuxi.utils.logging_config import logger


class RealtimeSessionManager:
    def __init__(self) -> None:
        self._handler = SmallWebRTCRequestHandler()
        self._sessions: dict[str, RealtimeSessionConfig] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def create_session(self, *, uid: str, agent_slug: str, thread_id: str) -> RealtimeSessionConfig:
        session_id = str(uuid.uuid4())
        config = RealtimeSessionConfig(
            session_id=session_id,
            uid=uid,
            agent_slug=agent_slug,
            thread_id=thread_id,
        )
        self._sessions[session_id] = config
        return config

    async def offer(self, session_id: str, request: SmallWebRTCRequest):
        config = self._sessions.get(session_id)
        if not config:
            raise LookupError("realtime session does not exist")

        async def start_pipeline(connection) -> None:
            previous = self._tasks.get(session_id)
            if previous and not previous.done():
                previous.cancel()
            task = asyncio.create_task(run_realtime_pipeline(connection, config))
            self._tasks[session_id] = task
            task.add_done_callback(lambda completed: self._pipeline_finished(session_id, completed))

        return await self._handler.handle_web_request(request, start_pipeline)

    async def add_ice_candidates(self, session_id: str, request: SmallWebRTCPatchRequest) -> None:
        if session_id not in self._sessions:
            raise LookupError("realtime session does not exist")
        await self._handler.handle_patch_request(request)

    def _pipeline_finished(self, session_id: str, task: asyncio.Task) -> None:
        if self._tasks.get(session_id) is task:
            self._tasks.pop(session_id, None)
            self._sessions.pop(session_id, None)
        if task.cancelled():
            return
        if error := task.exception():
            logger.error(f"Realtime pipeline failed: session={session_id} error={error}")

    async def close(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._sessions.clear()
        await self._handler.close()


realtime_session_manager = RealtimeSessionManager()
