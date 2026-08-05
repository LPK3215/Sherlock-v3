"""Pipecat cascade pipeline backed directly by Yuxi AgentRun services."""

from __future__ import annotations

import asyncio
import base64
import io
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from PIL import Image
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    InterruptionFrame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    UserImageRawFrame,
    UserImageRequestFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame, RTVIUICommandFrame
from pipecat.services.llm_service import LLMService
from pipecat.services.settings import LLMSettings
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.workers.runner import WorkerRunner

from yuxi.realtime.speech import create_stt_service, create_tts_service
from yuxi.realtime.webrtc import bind_remote_media_sources, refresh_screen_video_track, request_video_keyframe
from yuxi.services.agent_run_service import (
    cancel_agent_run_view,
    create_agent_run_view,
    get_agent_run_view,
)
from yuxi.services.input_message_service import build_chat_input_message
from yuxi.services.run_queue_service import list_run_stream_events
from yuxi.storage.postgres.manager import pg_manager
from yuxi.utils.logging_config import logger


@dataclass(frozen=True, slots=True)
class RealtimeSessionConfig:
    session_id: str
    uid: str
    agent_slug: str
    thread_id: str


class RealtimeAgentRun:
    def __init__(self, config: RealtimeSessionConfig) -> None:
        self.config = config
        self.active_run_id: str | None = None
        self.interrupted_run_id: str | None = None

    async def run_turn(
        self,
        query: str,
        image_content: str | None = None,
        image_meta: dict | None = None,
        *,
        include_started: bool = False,
    ):
        request_id = f"realtime-{self.config.session_id}-{datetime.now(UTC).timestamp()}"
        metadata = {
            "request_id": request_id,
            "source": "realtime",
            "channel": "voice",
            "realtime_session_id": self.config.session_id,
        }
        if image_meta:
            metadata["image_meta"] = image_meta

        async with pg_manager.get_async_session_context() as db:
            run = await create_agent_run_view(
                input_message=build_chat_input_message(query, image_content),
                agent_slug=self.config.agent_slug,
                thread_id=self.config.thread_id,
                meta=metadata,
                current_uid=self.config.uid,
                db=db,
            )

        run_id = str(run["run_id"])
        self.active_run_id = run_id
        if include_started:
            yield {
                "event_type": "run.started",
                "run_id": run_id,
                "thread_id": self.config.thread_id,
                "payload": {"agent_slug": self.config.agent_slug},
            }
        cursor = "0-0"
        try:
            while True:
                events = await list_run_stream_events(run_id, after_seq=cursor, limit=200)
                for event in events:
                    cursor = str(event["seq"])
                    yield event
                    if event["event_type"] == "end":
                        return
                await asyncio.sleep(0.1)
        finally:
            if self.active_run_id == run_id:
                self.active_run_id = None

    async def cancel(self) -> None:
        run_id = self.active_run_id
        if not run_id:
            return
        async with pg_manager.get_async_session_context() as db:
            await cancel_agent_run_view(run_id=run_id, current_uid=self.config.uid, db=db)
        # Cancellation is cooperative in the worker.  Wait until the row is
        # terminal so the next turn cannot race Yuxi's run_busy guard.
        for _ in range(50):
            async with pg_manager.get_async_session_context() as db:
                run = (await get_agent_run_view(run_id=run_id, current_uid=self.config.uid, db=db))["run"]
            if run.get("status") in {"completed", "failed", "cancelled", "interrupted"}:
                return
            await asyncio.sleep(0.1)

    async def resume_turn(self, answer: object):
        """Resume the latest interrupted Yuxi run with the user's approval answer."""
        parent_run_id = self.interrupted_run_id
        if not parent_run_id:
            raise RuntimeError("没有可恢复的中断运行")
        request_id = f"realtime-resume-{self.config.session_id}-{datetime.now(UTC).timestamp()}"
        metadata = {
            "request_id": request_id,
            "source": "realtime",
            "channel": "voice",
            "realtime_session_id": self.config.session_id,
        }
        async with pg_manager.get_async_session_context() as db:
            run = await create_agent_run_view(
                input_message=None,
                resume=answer,
                created_by_run_id=parent_run_id,
                agent_slug=self.config.agent_slug,
                thread_id=self.config.thread_id,
                meta=metadata,
                current_uid=self.config.uid,
                db=db,
            )
        run_id = str(run["run_id"])
        self.active_run_id = run_id
        self.interrupted_run_id = None
        yield {"event_type": "run.started", "run_id": run_id, "thread_id": self.config.thread_id,
               "payload": {"run_type": "resume", "created_by_run_id": parent_run_id}}
        cursor = "0-0"
        try:
            while True:
                events = await list_run_stream_events(run_id, after_seq=cursor, limit=200)
                for event in events:
                    cursor = str(event["seq"])
                    yield event
                    if event["event_type"] == "end":
                        return
                await asyncio.sleep(0.1)
        finally:
            if self.active_run_id == run_id:
                self.active_run_id = None


class FrameBroker(FrameProcessor):
    def __init__(
        self,
        config: RealtimeSessionConfig,
        request_keyframe: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        super().__init__(name=f"FrameBroker({config.session_id})")
        self.config = config
        self.user_id = ""
        self._request_keyframe = request_keyframe
        self._pending: dict[int, asyncio.Future[UserImageRawFrame]] = {}

    async def capture(self, source: Literal["camera", "screen"], wait_fresh_ms: int = 3000) -> dict:
        if not self.user_id:
            raise RuntimeError("realtime media client is not connected")

        request = UserImageRequestFrame(
            user_id=self.user_id,
            append_to_context=False,
            video_source="screenVideo" if source == "screen" else "camera",
        )
        future = asyncio.get_running_loop().create_future()
        self._pending[request.id] = future
        await self.push_frame(request, FrameDirection.UPSTREAM)
        if source == "screen":
            await asyncio.sleep(0)
        if self._request_keyframe:
            await self._request_keyframe(source)
        try:
            frame = await asyncio.wait_for(future, timeout=max(100, min(wait_fresh_ms, 5000)) / 1000)
        finally:
            self._pending.pop(request.id, None)

        image = Image.frombytes(frame.format or "RGB", frame.size, frame.image)
        image.thumbnail((1280, 1280))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=82, optimize=True)
        return {
            "session_id": self.config.session_id,
            "source": source,
            "mime_type": "image/jpeg",
            "width": image.width,
            "height": image.height,
            "captured_at": datetime.now(UTC).isoformat(),
            "data_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
        }

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, UserImageRawFrame) and frame.request:
            future = self._pending.get(frame.request.id)
            if future and not future.done():
                future.set_result(frame)
                return
        await self.push_frame(frame, direction)


_frame_brokers: dict[str, FrameBroker] = {}


async def capture_realtime_frame(
    session_id: str,
    uid: str,
    source: Literal["camera", "screen"],
    wait_fresh_ms: int,
) -> dict:
    broker = _frame_brokers.get(session_id)
    if not broker:
        raise LookupError("realtime session is not active")
    if broker.config.uid != uid:
        raise PermissionError("realtime session user mismatch")
    return await broker.capture(source, wait_fresh_ms)


class YuxiRealtimeLLMService(LLMService):
    def __init__(self, agent_run: RealtimeAgentRun, frame_broker: FrameBroker) -> None:
        super().__init__(
            name="LLM(Yuxi AgentRun)",
            settings=LLMSettings(
                model=None,
                system_instruction=None,
                temperature=None,
                max_tokens=None,
                top_p=None,
                top_k=None,
                frequency_penalty=None,
                presence_penalty=None,
                seed=None,
                filter_incomplete_user_turns=None,
                user_turn_completion_config=None,
            ),
        )
        self._agent_run = agent_run
        self._frame_broker = frame_broker
        self._media_source: Literal["none", "camera", "screen"] | None = None
        self._run_lock = asyncio.Lock()

    async def process_frame(self, frame, direction: FrameDirection):
        if isinstance(frame, InterruptionFrame):
            # Pipecat's interruption only stops local audio generation.  The
            # Yuxi AgentRun is a separate worker-backed execution and must be
            # cancelled explicitly before the next user turn is created;
            # otherwise Yuxi's single-active-run guard returns run_busy.
            await self._agent_run.cancel()
            await self.push_frame(frame, direction)
            await super().process_frame(frame, direction)
            return

        await super().process_frame(frame, direction)
        if not isinstance(frame, LLMContextFrame):
            await self.push_frame(frame, direction)
            return

        query, image_content = _latest_user_input(frame.context)
        image_meta = None
        if self._media_source in {"camera", "screen"}:
            payload = await self._frame_broker.capture(self._media_source)
            image_content = payload["data_base64"]
            image_meta = {key: payload[key] for key in ("source", "captured_at", "width", "height", "mime_type")}
        await self._run_agent(query, image_content, image_meta)

    async def _run_agent(self, query: str, image_content: str | None, image_meta: dict | None) -> None:
        async with self._run_lock:
            await self.push_frame(LLMFullResponseStartFrame())
            await self.start_processing_metrics()
            try:
                async for event in self._agent_run.run_turn(
                    query,
                    image_content,
                    image_meta,
                    include_started=True,
                ):
                    realtime_payload = _realtime_event_payload(event)
                    await self.push_frame(
                        RTVIServerMessageFrame(
                            data={"type": "yuxi-agent-event", "payload": realtime_payload}
                        )
                    )
                    if realtime_payload.get("type") == "approval.required":
                        self._agent_run.interrupted_run_id = (
                            realtime_payload.get("run_id") or self._agent_run.active_run_id
                        )
                        await self.push_frame(
                            RTVIUICommandFrame(
                                command="yuxi.approval.required",
                                payload=realtime_payload,
                            )
                        )
                    for delta in _event_text_deltas(event):
                        await self._push_llm_text(delta)
                if image_content is not None:
                    self._media_source = None
            except asyncio.CancelledError:
                await self._agent_run.cancel()
                raise
            except Exception as exc:
                await self.push_error(error_msg=f"Yuxi AgentRun failed: {exc}", exception=exc)
            finally:
                await self.stop_processing_metrics()
                await self.push_frame(LLMFullResponseEndFrame())


async def run_realtime_pipeline(connection, config: RealtimeSessionConfig) -> None:
    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True, video_in_enabled=True),
    )
    transport_client = transport._client
    agent_run = RealtimeAgentRun(config)

    @connection.event_handler("track-started")
    async def on_track_started(connection, track):
        if refresh_screen_video_track(transport_client, connection, track):
            logger.debug("Refreshed screen input track after WebRTC renegotiation")

    async def request_keyframe(source: str) -> None:
        await request_video_keyframe(connection, source)

    frame_broker = FrameBroker(config, request_keyframe=request_keyframe)
    llm = YuxiRealtimeLLMService(agent_run, frame_broker)
    context = LLMContext(messages=[])
    vad = SileroVADAnalyzer(params=VADParams(stop_secs=0.8, start_secs=0.08, confidence=0.4))
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        realtime_service_mode=False,
        user_params=LLMUserAggregatorParams(vad_analyzer=vad),
    )
    worker = PipelineWorker(
        Pipeline(
            [
                transport.input(),
                frame_broker,
                create_stt_service(),
                user_aggregator,
                llm,
                create_tts_service(),
                transport.output(),
                assistant_aggregator,
            ]
        ),
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=None,
    )
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        bind_remote_media_sources(connection.pc)
        frame_broker.user_id = connection.pc_id
        _frame_brokers[config.session_id] = frame_broker
        logger.info(f"Realtime client connected: session={config.session_id} agent={config.agent_slug}")

    @worker.rtvi.event_handler("on_client_message")
    async def on_client_message(rtvi, message):
        if message.type == "yuxi.media.attach":
            source = message.data.get("source") if isinstance(message.data, dict) else None
            llm._media_source = source if source in {"none", "camera", "screen"} else None
        elif message.type == "yuxi.approval.answer":
            answer = message.data
            # RTVI versions differ on whether the client payload is exposed
            # directly or retains the outer ``d`` envelope.
            if isinstance(answer, dict) and set(answer) == {"d"}:
                answer = answer["d"]
            async with llm._run_lock:
                await llm.push_frame(LLMFullResponseStartFrame())
                try:
                    async for event in agent_run.resume_turn(answer):
                        realtime_payload = _realtime_event_payload(event)
                        await llm.push_frame(
                            RTVIServerMessageFrame(data={"type": "yuxi-agent-event", "payload": realtime_payload})
                        )
                        for delta in _event_text_deltas(event):
                            await llm._push_llm_text(delta)
                except Exception as exc:
                    await llm.push_error(error_msg=f"Yuxi AgentRun resume failed: {exc}", exception=exc)
                finally:
                    await llm.push_frame(LLMFullResponseEndFrame())

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        _frame_brokers.pop(config.session_id, None)
        await agent_run.cancel()
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=False)
    try:
        await runner.add_workers(worker)
        await runner.run()
    finally:
        _frame_brokers.pop(config.session_id, None)


def _latest_user_input(context: LLMContext) -> tuple[str, str | None]:
    for message in reversed(context.get_messages()):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip(), None
        if isinstance(content, list):
            text = "\n".join(
                part["text"]
                for part in content
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
            ).strip()
            image_content = next(
                (
                    _data_url_content(part.get("image_url"))
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "image_url"
                ),
                None,
            )
            if text or image_content:
                return text, image_content
    raise ValueError("没有可提交给 Yuxi 的用户消息")


def _data_url_content(image_url: Any) -> str | None:
    if isinstance(image_url, dict):
        image_url = image_url.get("url")
    marker = ";base64,"
    if isinstance(image_url, str) and image_url.startswith("data:image/") and marker in image_url:
        return image_url.split(marker, 1)[1]
    return None


def _event_text_deltas(event: dict) -> list[str]:
    envelope = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    chunks = []
    if isinstance(payload.get("chunk"), dict):
        chunks.append(payload["chunk"])
    if isinstance(payload.get("items"), list):
        chunks.extend(item for item in payload["items"] if isinstance(item, dict))
    return [
        stream_event["content"]
        for chunk in chunks
        if isinstance((stream_event := chunk.get("stream_event")), dict)
        and stream_event.get("type") == "message_delta"
        and isinstance(stream_event.get("content"), str)
        and stream_event["content"]
    ]


def _realtime_event_payload(event: dict) -> dict[str, Any]:
    """Adapt standard run events to the small event contract used by RTVI."""
    if event.get("event_type") == "run.started":
        return {
            "type": "run.started",
            "run_id": event.get("run_id"),
            "thread_id": event.get("thread_id"),
            "detail": event.get("payload") or {},
        }

    event_type = str(event.get("event_type") or "yuxi.event")
    envelope = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    run_id = envelope.get("run_id") or event.get("run_id")
    thread_id = envelope.get("thread_id") or event.get("thread_id")
    status = payload.get("status")

    if event_type == "interrupt":
        reason = payload.get("reason")
        chunk = payload.get("chunk") if isinstance(payload.get("chunk"), dict) else payload
        if reason == "cancelled":
            high_level_type = "run.cancelled"
        elif reason in {"human_approval", "ask_user_question_required", "human_approval_required"}:
            high_level_type = "approval.required"
        else:
            high_level_type = "yuxi.interrupt"
        detail: dict[str, Any] = {"reason": reason}
        if isinstance(chunk, dict):
            questions = chunk.get("questions")
            source = chunk.get("source")
            if isinstance(questions, list):
                detail["questions"] = questions
            if isinstance(source, str) and source:
                detail["source"] = source
            interrupt_info = chunk.get("interrupt")
            if isinstance(interrupt_info, dict):
                detail["interrupt_info"] = {
                    key: interrupt_info[key]
                    for key in ("questions", "source", "thread_id")
                    if key in interrupt_info
                }
    elif event_type == "error" or status == "failed":
        high_level_type = "run.failed"
        detail = payload
    elif event_type == "end" and status == "cancelled":
        high_level_type = "run.cancelled"
        detail = payload
    elif event_type == "end" and status == "failed":
        high_level_type = "run.failed"
        detail = payload
    elif event_type == "end" and status == "completed":
        high_level_type = "run.completed"
        detail = payload
    else:
        high_level_type = f"yuxi.{event_type}"
        detail = payload

    return {
        "type": high_level_type,
        "run_id": run_id,
        "thread_id": thread_id,
        "detail": detail,
        "event_type": event_type,
    }
