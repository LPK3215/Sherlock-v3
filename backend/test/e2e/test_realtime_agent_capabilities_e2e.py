from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest

from yuxi.agents.backends.sandbox import (
    ensure_thread_dirs,
    sandbox_id_for_thread,
    sandbox_outputs_dir,
    sandbox_workspace_dir,
)
from yuxi.agents.backends.sandbox.provider import sandbox_provisioner_token

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e, pytest.mark.slow]

RUN_TIMEOUT_SECONDS = 300


def _assert_ok(response: httpx.Response) -> None:
    assert response.status_code < 400, response.text


async def _create_agent(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    slug: str,
    uid: str,
    model: str | None,
    context: dict[str, Any] | None = None,
) -> None:
    context = dict(
        context
        or {
            "system_prompt": (
                "你是实时通道能力验证智能体。用户要求写文件时必须调用 write_file；"
                "用户要求读取文件时必须调用 read_file，并在最终回答中原样返回文件内容。"
                "如果系统提示中出现 REALTIME_MEMORY_MARKER，回答记忆问题时必须原样返回该标记。"
                "不要调用摄像头、屏幕、网络搜索、知识库或子智能体。"
            ),
            "tools": ["present_artifacts"],
            "skills": ["__e2e_none__"],
            "mcps": ["__e2e_none__"],
            "knowledges": ["__e2e_none__"],
            "subagents": ["__e2e_none__"],
        }
    )
    if model:
        context["model"] = model

    response = await client.post(
        "/api/agent",
        json={
            "name": f"Realtime capability E2E {slug[-8:]}",
            "slug": slug,
            "backend_id": "ChatbotAgent",
            "description": "Realtime AgentRun capability regression test",
            "config_json": {"context": context},
            "share_config": {"access_level": "user", "department_ids": [], "user_uids": [uid]},
            "is_subagent": False,
        },
        headers=headers,
    )
    _assert_ok(response)


async def _current_uid_and_model(
    client: httpx.AsyncClient,
    headers: dict[str, str],
) -> tuple[str, str | None]:
    me_response = await client.get("/api/auth/me", headers=headers)
    _assert_ok(me_response)
    uid = str(me_response.json().get("uid") or "")
    assert uid, me_response.text

    realtime_response = await client.get("/api/agent/sherlock-realtime", headers=headers)
    _assert_ok(realtime_response)
    realtime_context = ((realtime_response.json().get("agent") or {}).get("config_json") or {}).get("context") or {}
    model = str(realtime_context.get("model") or "").strip() or None
    assert model, realtime_response.text
    return uid, model


async def _cancel_run(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    run_id: str | None,
) -> None:
    if not run_id:
        return
    response = await client.post(f"/api/agent/runs/{run_id}/cancel", headers=headers)
    assert response.status_code < 500, response.text


async def _delete_sandbox(thread_id: str, uid: str) -> None:
    provisioner_url = os.getenv("SANDBOX_PROVISIONER_URL", "http://sandbox-provisioner:8002").rstrip("/")
    sandbox_id = sandbox_id_for_thread(thread_id, uid=uid)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.delete(
            f"{provisioner_url}/api/sandboxes/{sandbox_id}",
            headers={"Authorization": f"Bearer {sandbox_provisioner_token()}"},
        )
    assert response.status_code in {200, 404}, response.text


async def _create_thread(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    agent_slug: str,
) -> str:
    response = await client.post(
        "/api/chat/thread",
        json={
            "agent_id": agent_slug,
            "title": "realtime-capability-e2e",
            "metadata": {"source": "realtime", "channel": "voice"},
        },
        headers=headers,
    )
    _assert_ok(response)
    thread_id = response.json().get("thread_id") or response.json().get("id")
    assert thread_id, response.text
    return str(thread_id)


async def _create_run(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    agent_slug: str,
    thread_id: str,
    query: str,
) -> str:
    response = await client.post(
        "/api/agent/runs",
        json={
            "query": query,
            "agent_slug": agent_slug,
            "thread_id": thread_id,
            "meta": {
                "request_id": f"realtime-capability-e2e-{uuid.uuid4()}",
                "source": "realtime",
                "channel": "voice",
                "realtime_session_id": f"rt-capability-e2e-{uuid.uuid4()}",
            },
        },
        headers=headers,
    )
    _assert_ok(response)
    run_id = response.json().get("run_id")
    assert run_id, response.text
    return str(run_id)


async def _consume_run(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    run_id: str,
) -> tuple[list[dict[str, Any]], str]:
    chunks: list[dict[str, Any]] = []
    terminal_status = ""

    async def consume() -> None:
        nonlocal terminal_status
        async with client.stream(
            "GET",
            f"/api/agent/runs/{run_id}/events",
            params={"verbose": "false"},
            headers=headers,
        ) as response:
            _assert_ok(response)
            event = "message"
            data_lines: list[str] = []
            async for line in response.aiter_lines():
                if not line:
                    if data_lines:
                        payload = json.loads("\n".join(data_lines))
                        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
                        chunk = event_payload.get("chunk")
                        if isinstance(chunk, dict):
                            chunks.append(chunk)
                        items = event_payload.get("items")
                        if isinstance(items, list):
                            chunks.extend(item for item in items if isinstance(item, dict))
                        if event == "end":
                            terminal_status = str(event_payload.get("status") or "")
                            return
                    event = "message"
                    data_lines = []
                    continue
                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event = line.removeprefix("event:").strip() or "message"
                elif line.startswith("data:"):
                    data_lines.append(line.removeprefix("data:").strip())

    await asyncio.wait_for(consume(), timeout=RUN_TIMEOUT_SECONDS)
    return chunks, terminal_status


def _tool_names(chunks: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for chunk in chunks:
        stream_event = chunk.get("stream_event")
        if isinstance(stream_event, dict) and stream_event.get("name"):
            names.add(str(stream_event["name"]))
        event = chunk.get("event")
        data = event.get("data") if isinstance(event, dict) else None
        if isinstance(data, dict) and data.get("tool_name"):
            names.add(str(data["tool_name"]))
    return names


async def test_realtime_run_keeps_tools_checkpoint_history_and_workspace_memory(
    e2e_client: httpx.AsyncClient,
    e2e_headers: dict[str, str],
):
    uid, model = await _current_uid_and_model(e2e_client, e2e_headers)

    suffix = uuid.uuid4().hex[:8]
    agent_slug = f"realtime-capability-e2e-{suffix}"
    output_path = "/home/gem/user-data/outputs/realtime-capability.txt"
    file_marker = f"REALTIME_FILE_MARKER_{suffix}"
    memory_marker = f"REALTIME_MEMORY_MARKER_{suffix}"
    thread_id = ""
    first_run_id: str | None = None
    second_run_id: str | None = None
    memory_path: Path | None = None
    memory_existed = False
    original_memory = ""

    try:
        await _create_agent(
            e2e_client,
            e2e_headers,
            slug=agent_slug,
            uid=uid,
            model=model,
        )
        thread_id = await _create_thread(
            e2e_client,
            e2e_headers,
            agent_slug=agent_slug,
        )
        ensure_thread_dirs(thread_id, uid)
        memory_path = sandbox_workspace_dir(thread_id, uid) / "agents" / "MEMORY.md"
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_existed = memory_path.exists()
        original_memory = memory_path.read_text(encoding="utf-8") if memory_existed else ""
        memory_path.write_text(f"{original_memory.rstrip()}\n\n{memory_marker}\n", encoding="utf-8")

        first_run_id = await _create_run(
            e2e_client,
            e2e_headers,
            agent_slug=agent_slug,
            thread_id=thread_id,
            query=(f"必须调用 write_file，把下面标记原样写入 {output_path}，完成后只回复路径：\n{file_marker}"),
        )
        first_chunks, first_status = await _consume_run(
            e2e_client,
            e2e_headers,
            first_run_id,
        )
        assert first_status == "completed", first_chunks
        assert "write_file" in _tool_names(first_chunks), first_chunks

        second_run_id = await _create_run(
            e2e_client,
            e2e_headers,
            agent_slug=agent_slug,
            thread_id=thread_id,
            query=(f"必须调用 read_file 读取 {output_path}。最终回答必须同时原样包含文件标记和系统记忆标记。"),
        )
        second_chunks, second_status = await _consume_run(
            e2e_client,
            e2e_headers,
            second_run_id,
        )
        assert second_status == "completed", second_chunks
        assert "read_file" in _tool_names(second_chunks), second_chunks

        result_response = await e2e_client.get(
            f"/api/agent/runs/{second_run_id}/result",
            headers=e2e_headers,
        )
        _assert_ok(result_response)
        result_text = json.dumps(result_response.json(), ensure_ascii=False)
        assert file_marker in result_text, result_text
        assert memory_marker in result_text, result_text

        history_response = await e2e_client.get(
            f"/api/chat/thread/{thread_id}/history",
            headers=e2e_headers,
        )
        _assert_ok(history_response)
        history_text = json.dumps(history_response.json(), ensure_ascii=False)
        assert first_run_id in history_text
        assert second_run_id in history_text
        assert file_marker in history_text
        assert '"source": "realtime"' in history_text
    finally:
        for run_id in (second_run_id, first_run_id):
            await _cancel_run(e2e_client, e2e_headers, run_id)
        if memory_path is not None:
            if memory_existed:
                memory_path.write_text(original_memory, encoding="utf-8")
            else:
                memory_path.unlink(missing_ok=True)
        if thread_id:
            await _delete_sandbox(thread_id, uid)
        delete_response = await e2e_client.delete(f"/api/agent/{agent_slug}", headers=e2e_headers)
        assert delete_response.status_code in {200, 404}, delete_response.text


async def test_realtime_run_calls_configured_mcp_tool(
    e2e_client: httpx.AsyncClient,
    e2e_headers: dict[str, str],
):
    uid, model = await _current_uid_and_model(e2e_client, e2e_headers)
    suffix = uuid.uuid4().hex[:8]
    mcp_slug = f"realtime-e2e-{suffix}"
    agent_slug = f"realtime-mcp-e2e-{suffix}"
    marker = f"REALTIME_MCP_MARKER_{suffix}"
    run_id: str | None = None
    thread_id = ""
    mcp_created = False
    mcp_server_code = (
        "from mcp.server.fastmcp import FastMCP\n"
        "server = FastMCP('realtime-e2e')\n"
        "@server.tool()\n"
        "def realtime_echo(marker: str) -> str:\n"
        "    return marker\n"
        "server.run(transport='stdio')\n"
    )

    try:
        create_mcp_response = await e2e_client.post(
            "/api/system/mcp-servers",
            json={
                "slug": mcp_slug,
                "name": f"Realtime E2E {suffix}",
                "transport": "stdio",
                "command": "python",
                "args": ["-c", mcp_server_code],
                "description": "Temporary realtime MCP E2E server",
            },
            headers=e2e_headers,
        )
        _assert_ok(create_mcp_response)
        mcp_created = True

        test_mcp_response = await e2e_client.post(
            f"/api/system/mcp-servers/{mcp_slug}/test",
            headers=e2e_headers,
        )
        _assert_ok(test_mcp_response)
        assert test_mcp_response.json().get("tool_count") == 1

        await _create_agent(
            e2e_client,
            e2e_headers,
            slug=agent_slug,
            uid=uid,
            model=model,
            context={
                "system_prompt": "用户提供标记时必须调用 realtime_echo，并原样返回工具结果。",
                "tools": [],
                "skills": [],
                "mcps": [mcp_slug],
                "knowledges": [],
                "subagents": ["__e2e_none__"],
            },
        )
        thread_id = await _create_thread(e2e_client, e2e_headers, agent_slug=agent_slug)
        run_id = await _create_run(
            e2e_client,
            e2e_headers,
            agent_slug=agent_slug,
            thread_id=thread_id,
            query=f"必须调用 realtime_echo，marker 参数必须是 {marker}。",
        )

        chunks, terminal_status = await _consume_run(e2e_client, e2e_headers, run_id)
        result_response = await e2e_client.get(f"/api/agent/runs/{run_id}/result", headers=e2e_headers)
        _assert_ok(result_response)

        assert terminal_status == "completed", chunks
        assert "realtime_echo" in _tool_names(chunks), chunks
        assert marker in json.dumps(result_response.json(), ensure_ascii=False)
    finally:
        await _cancel_run(e2e_client, e2e_headers, run_id)
        if thread_id:
            await _delete_sandbox(thread_id, uid)
        delete_agent_response = await e2e_client.delete(f"/api/agent/{agent_slug}", headers=e2e_headers)
        assert delete_agent_response.status_code in {200, 404}, delete_agent_response.text
        if mcp_created:
            delete_mcp_response = await e2e_client.delete(
                f"/api/system/mcp-servers/{mcp_slug}",
                headers=e2e_headers,
            )
            assert delete_mcp_response.status_code in {200, 404}, delete_mcp_response.text


async def test_realtime_skill_activates_and_executes_gated_tool(
    e2e_client: httpx.AsyncClient,
    e2e_headers: dict[str, str],
):
    uid, model = await _current_uid_and_model(e2e_client, e2e_headers)
    sync_response = await e2e_client.post("/api/system/skills/builtin/sync", headers=e2e_headers)
    _assert_ok(sync_response)
    assert any(item.get("slug") == "image-gen" for item in sync_response.json().get("data", []))

    suffix = uuid.uuid4().hex[:8]
    agent_slug = f"realtime-skill-e2e-{suffix}"
    filename = f"realtime-skill-{suffix}.txt"
    output_path = f"/home/gem/user-data/outputs/{filename}"
    marker = f"REALTIME_SKILL_MARKER_{suffix}"
    thread_id = ""
    run_id: str | None = None

    try:
        await _create_agent(
            e2e_client,
            e2e_headers,
            slug=agent_slug,
            uid=uid,
            model=model,
            context={
                "system_prompt": (
                    "这是实时 Skill 门控测试。必须先调用 read_file 读取 "
                    "/home/gem/skills/image-gen/SKILL.md，再调用 present_artifacts 一次展示用户指定的现有文件。"
                    "不要生成图片、不要执行代码、不要调用网络。完成后只回复文件路径。"
                ),
                "tools": [],
                "skills": ["image-gen"],
                "mcps": [],
                "knowledges": [],
                "subagents": ["__e2e_none__"],
            },
        )
        thread_id = await _create_thread(e2e_client, e2e_headers, agent_slug=agent_slug)
        ensure_thread_dirs(thread_id, uid)
        (sandbox_outputs_dir(thread_id) / filename).write_text(marker, encoding="utf-8")
        run_id = await _create_run(
            e2e_client,
            e2e_headers,
            agent_slug=agent_slug,
            thread_id=thread_id,
            query=f"按系统要求激活 Skill，并展示已存在的文件 {output_path}。",
        )

        chunks, terminal_status = await _consume_run(e2e_client, e2e_headers, run_id)
        result_response = await e2e_client.get(f"/api/agent/runs/{run_id}/result", headers=e2e_headers)
        _assert_ok(result_response)
        evidence = json.dumps({"chunks": chunks, "result": result_response.json()}, ensure_ascii=False)

        assert terminal_status == "completed", chunks
        tool_names = _tool_names(chunks)
        assert "read_file" in tool_names, chunks
        assert "present_artifacts" in tool_names, chunks
        assert output_path in evidence
    finally:
        await _cancel_run(e2e_client, e2e_headers, run_id)
        if thread_id:
            await _delete_sandbox(thread_id, uid)
        delete_agent_response = await e2e_client.delete(f"/api/agent/{agent_slug}", headers=e2e_headers)
        assert delete_agent_response.status_code in {200, 404}, delete_agent_response.text


async def test_realtime_run_emits_summary_compression_events(
    e2e_client: httpx.AsyncClient,
    e2e_headers: dict[str, str],
):
    uid, model = await _current_uid_and_model(e2e_client, e2e_headers)
    suffix = uuid.uuid4().hex[:8]
    mcp_slug = f"realtime-summary-e2e-{suffix}"
    agent_slug = f"realtime-summary-e2e-{suffix}"
    marker = f"REALTIME_SUMMARY_MARKER_{suffix}"
    run_id: str | None = None
    thread_id = ""
    mcp_created = False
    mcp_server_code = (
        "from mcp.server.fastmcp import FastMCP\n"
        "server = FastMCP('realtime-summary-e2e')\n"
        "@server.tool()\n"
        "def large_context(marker: str) -> str:\n"
        "    return marker + '\\n' + ('summary payload ' * 3000)\n"
        "server.run(transport='stdio')\n"
    )

    try:
        create_mcp_response = await e2e_client.post(
            "/api/system/mcp-servers",
            json={
                "slug": mcp_slug,
                "name": f"Realtime Summary E2E {suffix}",
                "transport": "stdio",
                "command": "python",
                "args": ["-c", mcp_server_code],
                "description": "Temporary realtime summary E2E server",
            },
            headers=e2e_headers,
        )
        _assert_ok(create_mcp_response)
        mcp_created = True

        await _create_agent(
            e2e_client,
            e2e_headers,
            slug=agent_slug,
            uid=uid,
            model=model,
            context={
                "system_prompt": "必须调用 large_context 一次，然后只回复收到标记。",
                "tools": [],
                "skills": [],
                "mcps": [mcp_slug],
                "knowledges": [],
                "subagents": ["__e2e_none__"],
                "summary_threshold": 1,
                "summary_keep_messages": 1,
                "summary_tool_result_token_limit": 10000,
                "summary_l2_trigger_ratio": 100.0,
            },
        )
        thread_id = await _create_thread(e2e_client, e2e_headers, agent_slug=agent_slug)
        run_id = await _create_run(
            e2e_client,
            e2e_headers,
            agent_slug=agent_slug,
            thread_id=thread_id,
            query=f"必须调用 large_context，marker 参数是 {marker}。",
        )

        chunks, terminal_status = await _consume_run(e2e_client, e2e_headers, run_id)
        compression_statuses = [
            str((chunk.get("compression") or {}).get("status") or "")
            for chunk in chunks
            if chunk.get("status") == "context_compression" and isinstance(chunk.get("compression"), dict)
        ]

        assert terminal_status == "completed", chunks
        assert "large_context" in _tool_names(chunks), chunks
        assert "started" in compression_statuses, chunks
        assert "completed" in compression_statuses, chunks
    finally:
        await _cancel_run(e2e_client, e2e_headers, run_id)
        if thread_id:
            await _delete_sandbox(thread_id, uid)
        delete_agent_response = await e2e_client.delete(f"/api/agent/{agent_slug}", headers=e2e_headers)
        assert delete_agent_response.status_code in {200, 404}, delete_agent_response.text
        if mcp_created:
            delete_mcp_response = await e2e_client.delete(
                f"/api/system/mcp-servers/{mcp_slug}",
                headers=e2e_headers,
            )
            assert delete_mcp_response.status_code in {200, 404}, delete_mcp_response.text
