from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from yuxi.realtime import pipeline as realtime_pipeline
from yuxi.repositories.agent_repository import (
    REALTIME_AGENT_MODEL,
    REALTIME_AGENT_SLUG,
    REALTIME_AGENT_SYSTEM_PROMPT,
    AgentRepository,
    is_builtin_agent,
)


@pytest.mark.asyncio
async def test_realtime_turn_uses_yuxi_agent_run_and_internal_events(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    @asynccontextmanager
    async def db_session():
        yield object()

    async def create_run(**kwargs):
        captured.update(kwargs)
        return {"run_id": "run-1"}

    async def list_events(run_id: str, **kwargs):
        assert run_id == "run-1"
        return [
            {
                "seq": "1-0",
                "event_type": "end",
                "payload": {"schema_version": 1, "event": "end", "payload": {"status": "completed"}},
            }
        ]

    monkeypatch.setattr(realtime_pipeline.pg_manager, "get_async_session_context", db_session)
    monkeypatch.setattr(realtime_pipeline, "create_agent_run_view", create_run)
    monkeypatch.setattr(realtime_pipeline, "list_run_stream_events", list_events)
    runtime = realtime_pipeline.RealtimeAgentRun(
        realtime_pipeline.RealtimeSessionConfig(
            session_id="session-1",
            uid="user-1",
            agent_slug="agent-1",
            thread_id="thread-1",
        )
    )

    events = [event async for event in runtime.run_turn("你好")]

    assert events[0]["event_type"] == "end"
    assert captured["agent_slug"] == "agent-1"
    assert captured["thread_id"] == "thread-1"
    assert captured["current_uid"] == "user-1"
    assert captured["meta"]["source"] == "realtime"
    assert captured["meta"]["realtime_session_id"] == "session-1"


def test_yuxi_message_delta_is_forwarded_to_tts():
    event = {
        "payload": {
            "schema_version": 1,
            "event": "message",
            "payload": {
                "chunk": {
                    "stream_event": {"type": "message_delta", "content": "你好"},
                }
            },
        }
    }

    assert realtime_pipeline._event_text_deltas(event) == ["你好"]


@pytest.mark.asyncio
async def test_realtime_agent_is_registered_with_model_and_prompt(monkeypatch: pytest.MonkeyPatch):
    repository = AgentRepository(None)
    captured = {}

    async def ensure_builtin(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(repository, "_ensure_builtin_agent", ensure_builtin)

    await repository.ensure_realtime_agent()

    assert captured["slug"] == REALTIME_AGENT_SLUG
    assert captured["config_context"]["model"] == REALTIME_AGENT_MODEL
    assert captured["config_context"]["system_prompt"] == REALTIME_AGENT_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_existing_realtime_agent_migrates_from_legacy_model(monkeypatch: pytest.MonkeyPatch):
    agent = SimpleNamespace(
        config_json={
            "context": {
                "model": "siliconflow-cn:Qwen/Qwen3-VL-8B-Instruct",
                "system_prompt": "custom prompt",
            }
        },
        updated_by="admin",
        updated_at=None,
    )

    class Db:
        committed = False
        refreshed = False

        async def commit(self):
            self.committed = True

        async def refresh(self, value):
            assert value is agent
            self.refreshed = True

    db = Db()
    repository = AgentRepository(db)

    async def get_by_slug(slug):
        assert slug == REALTIME_AGENT_SLUG
        return agent

    monkeypatch.setattr(repository, "get_by_slug", get_by_slug)

    result = await repository.ensure_realtime_agent()

    assert result is agent
    assert agent.config_json["context"]["model"] == REALTIME_AGENT_MODEL
    assert agent.config_json["context"]["system_prompt"] == "custom prompt"
    assert db.committed is True
    assert db.refreshed is True


def test_realtime_agent_is_protected_as_builtin():
    agent = type("Agent", (), {"slug": REALTIME_AGENT_SLUG})()

    assert is_builtin_agent(agent)
