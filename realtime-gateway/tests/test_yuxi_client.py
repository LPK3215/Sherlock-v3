from __future__ import annotations

import json

import httpx
import pytest

from yuxi_client import (
    YuxiAgentClient,
    YuxiRunEvent,
    YuxiSessionConfig,
    event_text_deltas,
    normalized_event,
    parse_sse_lines,
)


@pytest.mark.asyncio
async def test_parse_sse_lines_preserves_event_id_and_multiline_data():
    async def lines():
        for line in [
            "event: messages",
            "id: 10-0",
            'data: {"run_id":"run-1",',
            'data: "payload":{"chunk":{"status":"loading"}}}',
            "",
        ]:
            yield line

    events = [event async for event in parse_sse_lines(lines())]

    assert len(events) == 1
    assert events[0].event == "messages"
    assert events[0].seq == "10-0"
    assert events[0].data["run_id"] == "run-1"


@pytest.mark.asyncio
async def test_run_turn_uses_standard_yuxi_run_and_stream_contract():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST" and request.url.path == "/api/chat/thread":
            return httpx.Response(200, json={"id": "thread-1"})
        if request.method == "POST" and request.url.path == "/api/agent/runs":
            return httpx.Response(
                200,
                json={
                    "run_id": "run-1",
                    "thread_id": "thread-1",
                    "request_id": "request-1",
                    "status": "pending",
                },
            )
        if request.method == "GET" and request.url.path == "/api/agent/runs/run-1/events":
            sse = (
                "event: messages\n"
                "id: 1-0\n"
                'data: {"run_id":"run-1","thread_id":"thread-1","payload":{"chunk":{"status":"loading","stream_event":{"type":"message_delta","message_id":"m1","content":"你好"}}}}\n\n'
                "event: end\n"
                "id: 2-0\n"
                'data: {"run_id":"run-1","thread_id":"thread-1","payload":{"status":"completed"}}\n\n'
            )
            return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})
        return httpx.Response(404, json={"detail": "not found"})

    config = YuxiSessionConfig(
        base_url="http://yuxi.test",
        access_token="secret-token",
        agent_slug="assistant",
        session_id="rt-session-1",
    )
    client = YuxiAgentClient(config, transport=httpx.MockTransport(handler))
    try:
        events = [event async for event in client.run_turn("你好")]
    finally:
        await client.close()

    assert [event.event for event in events] == ["run.created", "messages", "end"]
    assert event_text_deltas(events[1]) == ["你好"]
    assert normalized_event(events[1])["type"] == "assistant.text.delta"
    assert normalized_event(events[2])["type"] == "run.completed"
    assert [request.url.path for request in requests] == [
        "/api/chat/thread",
        "/api/agent/runs",
        "/api/agent/runs/run-1/events",
    ]
    assert all(request.headers["authorization"] == "Bearer secret-token" for request in requests)
    run_request = next(request for request in requests if request.url.path == "/api/agent/runs")
    assert b'"realtime_session_id":"rt-session-1"' in run_request.content


@pytest.mark.asyncio
async def test_new_turn_cancels_active_run_and_retries_on_same_thread():
    requests: list[tuple[str, str]] = []
    create_attempts = 0
    active_run_checks = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active_run_checks, create_attempts
        requests.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/api/agent/runs":
            create_attempts += 1
            if create_attempts == 1:
                return httpx.Response(409, json={"detail": "thread already has an active run"})
            return httpx.Response(
                200,
                json={
                    "run_id": "run-new",
                    "thread_id": "thread-1",
                    "request_id": "request-new",
                    "status": "pending",
                },
            )
        if request.method == "GET" and request.url.path == "/api/agent/thread/thread-1/active_run":
            active_run_checks += 1
            if active_run_checks == 1:
                return httpx.Response(200, json={"run": {"id": "run-old"}})
            return httpx.Response(200, json={"run": None})
        if request.method == "POST" and request.url.path == "/api/agent/runs/run-old/cancel":
            return httpx.Response(200, json={"status": "cancelling"})
        if request.method == "GET" and request.url.path == "/api/agent/runs/run-new/events":
            return httpx.Response(
                200,
                text=(
                    "event: end\n"
                    "id: 1-0\n"
                    'data: {"run_id":"run-new","thread_id":"thread-1","payload":{"status":"completed"}}\n\n'
                ),
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(404, json={"detail": "not found"})

    config = YuxiSessionConfig(
        base_url="http://yuxi.test",
        access_token="secret-token",
        agent_slug="assistant",
        thread_id="thread-1",
    )
    client = YuxiAgentClient(config, transport=httpx.MockTransport(handler))
    try:
        events = [event async for event in client.run_turn("新的问题")]
    finally:
        await client.close()

    assert [event.event for event in events] == ["run.created", "end"]
    assert events[0].data["run_id"] == "run-new"
    assert requests == [
        ("POST", "/api/agent/runs"),
        ("GET", "/api/agent/thread/thread-1/active_run"),
        ("POST", "/api/agent/runs/run-old/cancel"),
        ("GET", "/api/agent/thread/thread-1/active_run"),
        ("POST", "/api/agent/runs"),
        ("GET", "/api/agent/runs/run-new/events"),
    ]


@pytest.mark.asyncio
async def test_interrupt_answer_creates_resume_run_for_interrupted_parent():
    run_bodies: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/agent/runs":
            run_bodies.append(json.loads(request.content))
            run_id = "run-parent" if len(run_bodies) == 1 else "run-resume"
            return httpx.Response(
                200,
                json={
                    "run_id": run_id,
                    "thread_id": "thread-1",
                    "request_id": f"request-{len(run_bodies)}",
                    "status": "pending",
                },
            )
        if request.method == "GET" and request.url.path == "/api/agent/runs/run-parent/events":
            return httpx.Response(
                200,
                text=(
                    "event: interrupt\n"
                    "id: 1-0\n"
                    'data: {"run_id":"run-parent","thread_id":"thread-1","payload":{"reason":"ask_user_question_required","chunk":{"status":"ask_user_question_required","questions":[{"question_id":"choice","question":"选择方案","options":[{"label":"方案 A","value":"a"}],"multi_select":false,"allow_other":true}]}}}\n\n'
                    "event: end\n"
                    "id: 2-0\n"
                    'data: {"run_id":"run-parent","thread_id":"thread-1","payload":{"status":"interrupted"}}\n\n'
                ),
                headers={"content-type": "text/event-stream"},
            )
        if request.method == "GET" and request.url.path == "/api/agent/runs/run-resume/events":
            return httpx.Response(
                200,
                text=(
                    "event: end\n"
                    "id: 1-0\n"
                    'data: {"run_id":"run-resume","thread_id":"thread-1","payload":{"status":"completed"}}\n\n'
                ),
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(404, json={"detail": "not found"})

    client = YuxiAgentClient(
        YuxiSessionConfig(
            base_url="http://yuxi.test",
            access_token="secret-token",
            agent_slug="assistant",
            thread_id="thread-1",
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        parent_events = [event async for event in client.run_turn("帮我选择方案")]
        resume_events = [event async for event in client.run_turn("方案 A")]
    finally:
        await client.close()

    assert normalized_event(parent_events[1])["type"] == "approval.required"
    assert client.pending_interrupt is None
    assert [event.event for event in resume_events] == ["run.created", "end"]
    assert run_bodies[1]["query"] is None
    assert run_bodies[1]["resume"] == "方案 A"
    assert run_bodies[1]["created_by_run_id"] == "run-parent"


@pytest.mark.asyncio
async def test_restore_pending_interrupt_replays_question_after_reconnect():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/api/agent/thread/thread-1/active_run":
            return httpx.Response(200, json={"run": {"id": "run-parent", "status": "interrupted"}})
        if request.method == "GET" and request.url.path == "/api/agent/runs/run-parent/events":
            return httpx.Response(
                200,
                text=(
                    "event: interrupt\n"
                    "id: 1-0\n"
                    'data: {"run_id":"run-parent","thread_id":"thread-1","payload":{"reason":"ask_user_question_required","chunk":{"status":"ask_user_question_required","questions":[{"question_id":"choice","question":"选择方案","options":[]}]}}}\n\n'
                    "event: end\n"
                    "id: 2-0\n"
                    'data: {"run_id":"run-parent","thread_id":"thread-1","payload":{"status":"interrupted"}}\n\n'
                ),
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(404, json={"detail": "not found"})

    client = YuxiAgentClient(
        YuxiSessionConfig(
            base_url="http://yuxi.test",
            access_token="secret-token",
            agent_slug="assistant",
            thread_id="thread-1",
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        event = await client.restore_pending_interrupt()
    finally:
        await client.close()

    assert event is not None
    assert normalized_event(event)["type"] == "approval.required"
    assert client.pending_interrupt["run_id"] == "run-parent"


def test_normalized_failed_event_preserves_error_detail():
    event = YuxiRunEvent(
        event="end",
        data={
            "run_id": "run-1",
            "thread_id": "thread-1",
            "payload": {
                "status": "failed",
                "chunk": {
                    "status": "error",
                    "error_type": "worker_error",
                    "error_message": "model unavailable",
                },
            },
        },
    )

    result = normalized_event(event)

    assert result["type"] == "run.failed"
    assert result["status"] == "failed"
    assert result["detail"] == {
        "error_type": "worker_error",
        "error_message": "model unavailable",
    }


def test_normalized_agent_state_projects_usage_and_subagent_details():
    usage_event = YuxiRunEvent(
        event="custom",
        data={
            "payload": {
                "name": "yuxi.agent_state",
                "agent_state": {"token_usage": {"total_tokens": 128}, "subagent_runs": []},
            }
        },
    )
    subagent_event = YuxiRunEvent(
        event="custom",
        data={
            "payload": {
                "name": "yuxi.agent_state",
                "agent_state": {
                    "token_usage": {"total_tokens": 256},
                    "subagent_runs": [{"subagent_slug": "research", "status": "running"}],
                },
            }
        },
    )

    assert normalized_event(usage_event) == {
        "type": "usage.updated",
        "seq": None,
        "run_id": None,
        "thread_id": None,
        "status": None,
        "detail": {"token_usage": {"total_tokens": 128}, "subagent_runs": []},
    }
    assert normalized_event(subagent_event)["type"] == "subagent.updated"
    assert normalized_event(subagent_event)["detail"]["subagent_runs"][0]["status"] == "running"


def test_normalized_context_compression_and_error_events():
    compression_event = YuxiRunEvent(
        event="custom",
        data={
            "payload": {
                "name": "yuxi.context_compression",
                "chunk": {
                    "status": "context_compression",
                    "compression": {"status": "completed", "summary_tokens": 320},
                },
            }
        },
    )
    error_event = YuxiRunEvent(
        event="error",
        data={
            "payload": {
                "retryable": True,
                "chunk": {
                    "status": "error",
                    "error_type": "tool_error",
                    "error_message": "tool unavailable",
                    "job_try": 2,
                },
            }
        },
    )

    assert normalized_event(compression_event)["type"] == "context.compression.completed"
    assert normalized_event(compression_event)["detail"] == {
        "status": "completed",
        "summary_tokens": 320,
    }
    assert normalized_event(error_event)["type"] == "run.error"
    assert normalized_event(error_event)["detail"] == {
        "error_type": "tool_error",
        "error_message": "tool unavailable",
        "retryable": True,
        "job_try": 2,
    }


def test_normalized_realtime_tool_events_are_projected_from_real_sse_envelope():
    started_event = YuxiRunEvent(
        event="custom",
        data={
            "run_id": "run-1",
            "thread_id": "thread-1",
            "payload": {
                "name": "yuxi.stream_event",
                "chunk": {
                    "status": "stream_event",
                    "event": {
                        "method": "tools",
                        "data": {
                            "event": "tool-started",
                            "tool_call_id": "call-1",
                            "tool_name": "write_file",
                            "input": {"file_path": "/tmp/result.txt"},
                        },
                    },
                },
            },
        },
    )
    event = YuxiRunEvent(
        event="custom",
        data={
            "run_id": "run-1",
            "thread_id": "thread-1",
            "payload": {
                "name": "yuxi.stream_event",
                "chunk": {
                    "status": "stream_event",
                    "event": {
                        "method": "tools",
                        "data": {
                            "event": "tool-finished",
                            "tool_call_id": "call-1",
                            "output": {
                                "content": "timed out",
                                "name": "write_file",
                                "status": "error",
                                "tool_call_id": "call-1",
                                "type": "tool",
                            },
                        },
                    }
                }
            }
        },
    )

    result = normalized_event(event)

    assert normalized_event(started_event) == {
        "type": "tool.started",
        "seq": None,
        "run_id": "run-1",
        "thread_id": "thread-1",
        "status": "started",
        "detail": {
            "tool_call_id": "call-1",
            "tool_name": "write_file",
            "input": {"file_path": "/tmp/result.txt"},
        },
    }
    assert result["type"] == "tool.failed"
    assert result["status"] == "error"
    assert result["detail"] == {
        "tool_call_id": "call-1",
        "tool_name": "write_file",
        "output": {
            "content": "timed out",
            "name": "write_file",
            "status": "error",
            "tool_call_id": "call-1",
            "type": "tool",
        },
    }


def test_session_config_requires_agent_and_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("YUXI_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("YUXI_AGENT_SLUG", raising=False)

    with pytest.raises(RuntimeError, match="access token"):
        YuxiSessionConfig.from_runner_body({})
