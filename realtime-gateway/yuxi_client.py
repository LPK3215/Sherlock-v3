"""HTTP/SSE client for the Yuxi AgentRun runtime."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx


class YuxiAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class YuxiSessionConfig:
    base_url: str
    access_token: str
    agent_slug: str
    session_id: str | None = None
    thread_id: str | None = None

    @classmethod
    def from_runner_body(cls, body: Any, *, session_id: str | None = None) -> "YuxiSessionConfig":
        payload = body if isinstance(body, dict) else {}
        base_url = os.getenv("YUXI_BASE_URL", "http://localhost:5050").strip().rstrip("/")
        access_token = str(
            payload.get("yuxi_access_token") or os.getenv("YUXI_ACCESS_TOKEN", "")
        ).strip()
        agent_slug = str(payload.get("agent_slug") or os.getenv("YUXI_AGENT_SLUG", "")).strip()
        thread_id = str(payload.get("thread_id") or os.getenv("YUXI_THREAD_ID", "")).strip() or None

        parsed_url = urlparse(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise RuntimeError("YUXI_BASE_URL must be an absolute HTTP(S) URL")
        if not access_token:
            raise RuntimeError("Missing Yuxi access token")
        if not agent_slug:
            raise RuntimeError("Missing Yuxi agent slug")

        return cls(
            base_url=base_url,
            access_token=access_token,
            agent_slug=agent_slug,
            session_id=session_id,
            thread_id=thread_id,
        )


@dataclass(frozen=True)
class YuxiRunEvent:
    event: str
    data: dict[str, Any]
    seq: str | None = None


class YuxiAgentClient:
    """Own one realtime session's Yuxi thread and active AgentRun."""

    def __init__(
        self, config: YuxiSessionConfig, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.config = config
        self.thread_id = config.thread_id
        self.active_run_id: str | None = None
        self.pending_interrupt: dict[str, Any] | None = None
        self._http = httpx.AsyncClient(
            base_url=config.base_url,
            headers={"Authorization": f"Bearer {config.access_token}"},
            timeout=httpx.Timeout(30.0, read=900.0),
            transport=transport,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def current_user_uid(self) -> str:
        response = await self._http.get("/api/auth/me")
        payload = self._response_json(response, "读取 Yuxi 用户身份失败")
        uid = payload.get("uid")
        if not uid:
            raise YuxiAPIError("Yuxi 用户响应缺少 uid")
        return str(uid)

    async def ensure_thread(self) -> str:
        if self.thread_id:
            return self.thread_id

        response = await self._http.post(
            "/api/chat/thread",
            json={
                "agent_id": self.config.agent_slug,
                "title": "Sherlock 实时对话",
                "metadata": {"source": "realtime", "channel": "voice"},
            },
        )
        payload = self._response_json(response, "创建 Yuxi 会话失败")
        thread_id = payload.get("thread_id") or payload.get("id")
        if not thread_id:
            raise YuxiAPIError("Yuxi 创建会话响应缺少 thread_id")
        self.thread_id = str(thread_id)
        return self.thread_id

    async def run_turn(
        self,
        query: str | None,
        *,
        image_content: str | None = None,
        image_meta: dict[str, Any] | None = None,
        resume: Any | None = None,
    ) -> AsyncIterator[YuxiRunEvent]:
        thread_id = await self.ensure_thread()
        pending_interrupt = self.pending_interrupt
        if pending_interrupt:
            resume = query if resume is None else resume
            query = None
            image_content = None
            image_meta = None
        elif resume is not None:
            raise YuxiAPIError("当前没有需要恢复的 Yuxi Agent Run", status_code=409)

        run = await self._create_run_after_active_run_finishes(
            query=query,
            image_content=image_content,
            image_meta=image_meta,
            thread_id=thread_id,
            resume=resume,
            created_by_run_id=pending_interrupt["run_id"] if pending_interrupt else None,
        )
        if pending_interrupt:
            self.pending_interrupt = None
        run_id = str(run["run_id"])
        self.active_run_id = run_id
        yield YuxiRunEvent(
            event="run.created",
            data={
                "run_id": run_id,
                "thread_id": thread_id,
                "request_id": run.get("request_id"),
                "status": run.get("status"),
            },
        )

        try:
            async for event in self.stream_run_events(run_id):
                self._update_pending_interrupt(event)
                yield event
        finally:
            if self.active_run_id == run_id:
                self.active_run_id = None

    async def cancel_active_run(self) -> None:
        run_id = self.active_run_id
        if not run_id:
            return
        response = await self._http.post(f"/api/agent/runs/{run_id}/cancel", json={})
        if response.status_code not in {200, 404, 409}:
            self._response_json(response, "取消 Yuxi Agent Run 失败")

    async def restore_pending_interrupt(self) -> YuxiRunEvent | None:
        if not self.thread_id:
            return None

        response = await self._http.get(f"/api/agent/thread/{self.thread_id}/active_run")
        payload = self._response_json(response, "查询 Yuxi 待恢复 Run 失败")
        run = payload.get("run")
        if not isinstance(run, dict) or run.get("status") != "interrupted":
            return None

        run_id = str(run.get("id") or run.get("run_id") or "").strip()
        if not run_id:
            raise YuxiAPIError("Yuxi 待恢复 Run 响应缺少 run_id")

        restored_event = None
        async for event in self.stream_run_events(run_id):
            if self._update_pending_interrupt(event):
                restored_event = event
        return restored_event

    async def stream_run_events(
        self, run_id: str, *, after_seq: str = "0-0"
    ) -> AsyncIterator[YuxiRunEvent]:
        headers = {"Accept": "text/event-stream"}
        if after_seq != "0-0":
            headers["Last-Event-ID"] = after_seq

        async with self._http.stream(
            "GET",
            f"/api/agent/runs/{run_id}/events",
            params={"verbose": "false", "after_seq": after_seq},
            headers=headers,
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                raise self._response_error(
                    response.status_code, body.decode(errors="replace"), "读取 Yuxi 事件失败"
                )
            async for event in parse_sse_lines(response.aiter_lines()):
                yield event

    async def _create_run_after_active_run_finishes(
        self,
        *,
        query: str | None,
        image_content: str | None,
        image_meta: dict[str, Any] | None,
        thread_id: str,
        resume: Any | None,
        created_by_run_id: str | None,
    ) -> dict[str, Any]:
        request_id = f"realtime-{uuid.uuid4()}"
        meta = {"request_id": request_id, "source": "realtime", "channel": "voice"}
        if self.config.session_id:
            meta["realtime_session_id"] = self.config.session_id
        if image_meta:
            meta["image_meta"] = image_meta
        body = {
            "query": query,
            "agent_slug": self.config.agent_slug,
            "thread_id": thread_id,
            "meta": meta,
            "image_content": image_content,
            "resume": resume,
            "created_by_run_id": created_by_run_id,
        }

        for attempt in range(2):
            response = await self._http.post("/api/agent/runs", json=body)
            if response.status_code != 409 or attempt == 1:
                payload = self._response_json(response, "创建 Yuxi Agent Run 失败")
                if not payload.get("run_id"):
                    raise YuxiAPIError("Yuxi Agent Run 响应缺少 run_id")
                return payload
            await self._wait_for_thread_release(thread_id)

        raise AssertionError("unreachable")

    async def _wait_for_thread_release(self, thread_id: str) -> None:
        for _ in range(50):
            response = await self._http.get(f"/api/agent/thread/{thread_id}/active_run")
            payload = self._response_json(response, "查询 Yuxi 活跃 Run 失败")
            run = payload.get("run")
            if not run:
                return
            run_id = run.get("id") or run.get("run_id")
            if run_id:
                self.active_run_id = str(run_id)
                await self.cancel_active_run()
            await asyncio.sleep(0.2)
        raise YuxiAPIError("等待上一条 Yuxi Agent Run 结束超时", status_code=409)

    def _update_pending_interrupt(self, event: YuxiRunEvent) -> bool:
        projection = normalized_event(event)
        if projection["type"] != "approval.required":
            return False

        run_id = str(projection.get("run_id") or "").strip()
        if not run_id:
            raise YuxiAPIError("Yuxi 审批事件缺少 run_id")
        self.pending_interrupt = {
            "run_id": run_id,
            "thread_id": projection.get("thread_id") or self.thread_id,
            "status": projection.get("status"),
            "detail": projection.get("detail") or {},
        }
        return True

    @staticmethod
    def _response_json(response: httpx.Response, message: str) -> dict[str, Any]:
        if response.status_code >= 400:
            raise YuxiAgentClient._response_error(response.status_code, response.text, message)
        try:
            payload = response.json()
        except ValueError as exc:
            raise YuxiAPIError(
                f"{message}: 响应不是 JSON", status_code=response.status_code
            ) from exc
        if not isinstance(payload, dict):
            raise YuxiAPIError(f"{message}: 响应格式错误", status_code=response.status_code)
        return payload

    @staticmethod
    def _response_error(status_code: int, body: str, message: str) -> YuxiAPIError:
        detail = body
        try:
            payload = json.loads(body)
            if isinstance(payload, dict):
                detail = str(payload.get("detail") or payload.get("message") or body)
        except ValueError:
            pass
        return YuxiAPIError(f"{message} ({status_code}): {detail[:500]}", status_code=status_code)


async def parse_sse_lines(lines: AsyncIterable[str]) -> AsyncIterator[YuxiRunEvent]:
    event_name = "message"
    event_id: str | None = None
    data_lines: list[str] = []

    async for line in lines:
        if not line:
            if data_lines:
                raw_data = "\n".join(data_lines)
                try:
                    payload = json.loads(raw_data)
                except ValueError as exc:
                    raise YuxiAPIError("Yuxi SSE 包含无效 JSON") from exc
                if isinstance(payload, dict):
                    yield YuxiRunEvent(event=event_name, data=payload, seq=event_id)
            event_name = "message"
            event_id = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if not separator:
            continue
        value = value.lstrip(" ")
        if field == "event":
            event_name = value or "message"
        elif field == "id":
            event_id = value or None
        elif field == "data":
            data_lines.append(value)

    if data_lines:
        payload = json.loads("\n".join(data_lines))
        if isinstance(payload, dict):
            yield YuxiRunEvent(event=event_name, data=payload, seq=event_id)


def iter_event_chunks(event: YuxiRunEvent) -> list[dict[str, Any]]:
    payload = event.data.get("payload")
    if not isinstance(payload, dict):
        return []
    chunks: list[dict[str, Any]] = []
    if isinstance(payload.get("chunk"), dict):
        chunks.append(payload["chunk"])
    if isinstance(payload.get("items"), list):
        chunks.extend(item for item in payload["items"] if isinstance(item, dict))
    return chunks


def event_text_deltas(event: YuxiRunEvent) -> list[str]:
    deltas: list[str] = []
    for chunk in iter_event_chunks(event):
        stream_event = chunk.get("stream_event")
        if not isinstance(stream_event, dict) or stream_event.get("type") != "message_delta":
            continue
        content = stream_event.get("content")
        if isinstance(content, str) and content:
            deltas.append(content)
    return deltas


def normalized_event(event: YuxiRunEvent) -> dict[str, Any]:
    event_type = f"yuxi.{event.event}"
    status = None
    detail: dict[str, Any] = {}

    if event.event == "run.created":
        event_type = "run.started"
        status = event.data.get("status")
        detail = event.data
    elif event.event == "end":
        payload = (
            event.data.get("payload") if isinstance(event.data.get("payload"), dict) else event.data
        )
        status = payload.get("status") if isinstance(payload, dict) else None
        event_type = {
            "completed": "run.completed",
            "cancelled": "run.cancelled",
            "failed": "run.failed",
            "interrupted": "agent.interrupted",
        }.get(str(status), "run.completed")
        terminal_chunk = payload.get("chunk") if isinstance(payload, dict) else None
        if isinstance(terminal_chunk, dict):
            detail = {
                key: terminal_chunk.get(key)
                for key in ("error_type", "error_message", "message")
                if terminal_chunk.get(key) is not None
            }
    elif event.event == "error":
        payload = event.data.get("payload") if isinstance(event.data.get("payload"), dict) else {}
        chunk = payload.get("chunk") if isinstance(payload.get("chunk"), dict) else {}
        status = str(chunk.get("status") or "error")
        event_type = "run.error"
        detail = {
            key: value
            for key in ("error_type", "error_message", "message", "retryable", "job_try")
            if (value := chunk.get(key, payload.get(key))) is not None
        }
    elif event.event == "interrupt":
        payload = event.data.get("payload") if isinstance(event.data.get("payload"), dict) else {}
        chunk = payload.get("chunk") if isinstance(payload.get("chunk"), dict) else {}
        status = str(chunk.get("status") or payload.get("reason") or "interrupted")
        event_type = (
            "approval.required"
            if status in {"human_approval", "human_approval_required", "ask_user_question_required"}
            else "agent.interrupted"
        )
        detail = {
            key: value
            for key in ("reason", "message", "questions", "interrupt_info")
            if (value := chunk.get(key, payload.get(key))) is not None
        }
    elif event.event == "custom":
        payload = event.data.get("payload") if isinstance(event.data.get("payload"), dict) else {}
        chunk = payload.get("chunk") if isinstance(payload.get("chunk"), dict) else {}
        name = str(payload.get("name") or "")
        status = str(chunk.get("status") or "") or None

        if name == "yuxi.agent_state":
            agent_state = payload.get("agent_state")
            if not isinstance(agent_state, dict):
                agent_state = chunk.get("agent_state") if isinstance(chunk.get("agent_state"), dict) else {}
            detail = agent_state
            if agent_state.get("subagent_runs"):
                event_type = "subagent.updated"
            elif agent_state.get("token_usage"):
                event_type = "usage.updated"
            else:
                event_type = "agent.state.updated"
        elif name == "yuxi.context_compression":
            compression = chunk.get("compression")
            detail = compression if isinstance(compression, dict) else {}
            compression_status = str(detail.get("status") or status or "updated")
            event_type = f"context.compression.{compression_status}"
        elif name == "yuxi.warning":
            event_type = "run.warning"
            detail = {
                key: chunk[key]
                for key in ("message", "error_type", "error_message")
                if chunk.get(key) is not None
            }
        elif name == "yuxi.stream_event":
            tool_projection = _normalize_tool_event(chunk.get("event"))
            if tool_projection:
                event_type, status, detail = tool_projection
    else:
        chunks = iter_event_chunks(event)
        if chunks:
            chunk = chunks[-1]
            status = chunk.get("status")
            stream_event = chunk.get("stream_event")
            if isinstance(stream_event, dict) and stream_event.get("type") == "message_delta":
                event_type = "assistant.text.delta"
                detail = {"content": stream_event.get("content", "")}
            elif tool_projection := _normalize_tool_event(chunk.get("event")):
                event_type, status, detail = tool_projection
            elif status in {"human_approval_required", "ask_user_question_required"}:
                event_type = "approval.required"

    return {
        "type": event_type,
        "seq": event.seq,
        "run_id": event.data.get("run_id"),
        "thread_id": event.data.get("thread_id"),
        "status": status,
        "detail": detail,
    }


def _normalize_tool_event(tool_event: Any) -> tuple[str, str, dict[str, Any]] | None:
    if not isinstance(tool_event, dict) or tool_event.get("method") != "tools":
        return None

    tool_data = tool_event.get("data") if isinstance(tool_event.get("data"), dict) else {}
    output = tool_data.get("output") if isinstance(tool_data.get("output"), dict) else {}
    is_finished = tool_data.get("event") == "tool-finished"
    is_failed = bool(tool_data.get("error")) or output.get("status") == "error"

    if is_failed:
        event_type = "tool.failed"
        status = "error"
    elif is_finished:
        event_type = "tool.completed"
        status = "completed"
    else:
        event_type = "tool.started"
        status = "started"

    detail = {
        key: tool_data.get(key)
        for key in ("tool_call_id", "tool_name", "input", "output", "error")
        if tool_data.get(key) is not None
    }
    if "tool_call_id" not in detail and output.get("tool_call_id"):
        detail["tool_call_id"] = output["tool_call_id"]
    if "tool_name" not in detail and output.get("name"):
        detail["tool_name"] = output["name"]
    return event_type, status, detail
