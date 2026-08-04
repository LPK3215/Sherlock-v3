from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from yuxi.agents.middlewares.skills import expand_skill_closure
from yuxi.agents.skills.buildin import BUILTIN_SKILLS
from yuxi.agents.mcp import service as mcp_service
from yuxi.agents.toolkits import career
from yuxi.agents.toolkits.registry import get_all_tool_instances, get_extra_metadata
from yuxi.agents.toolkits.service import resolve_configured_runtime_tools


class _FakeRecord:
    def to_dict(self):
        return {"id": 5, "uid": "worker-1", "record_type": "meeting"}


class _FakeRepository:
    calls = []

    def __init__(self, _db):
        pass

    async def create_record(self, **kwargs):
        self.calls.append(("create", kwargs))
        return _FakeRecord()

    async def list_records(self, **kwargs):
        self.calls.append(("list", kwargs))
        return [_FakeRecord()]


def _runtime(uid="worker-1"):
    return SimpleNamespace(context=SimpleNamespace(uid=uid))


@asynccontextmanager
async def _session_context():
    yield object()


def _patch_storage(monkeypatch):
    _FakeRepository.calls = []
    monkeypatch.setattr(career, "CareerRepository", _FakeRepository)
    monkeypatch.setattr(career.pg_manager, "get_async_session_context", _session_context)


def test_career_tools_are_registered_with_category():
    names = {item.name for item in get_all_tool_instances()}
    assert {"save_career_record", "list_career_records"} <= names
    assert get_extra_metadata("save_career_record").category == "career"


@pytest.mark.asyncio
async def test_career_tools_use_uid_and_reject_blank_summary(monkeypatch):
    _patch_storage(monkeypatch)
    with pytest.raises(ValueError, match="标题和摘要不能为空"):
        await career.save_career_record.coroutine(title="工作", summary=" ", runtime=_runtime())

    monkeypatch.setattr(career, "interrupt", lambda _payload: {"save_career_record": "confirm"})
    await career.save_career_record.coroutine(
        title="项目会议", summary="确认接口范围", record_type="meeting", runtime=_runtime()
    )
    await career.list_career_records.coroutine(runtime=_runtime("worker-2"), status="open", limit=7)

    assert _FakeRepository.calls[0][1]["uid"] == "worker-1"
    assert _FakeRepository.calls[1][1] == {"uid": "worker-2", "record_type": None, "status": "open", "limit": 7}


@pytest.mark.asyncio
async def test_career_record_requires_confirmation_before_persisting(monkeypatch):
    _patch_storage(monkeypatch)
    monkeypatch.setattr(career, "interrupt", lambda _payload: {"save_career_record": "cancel"})

    result = await career.save_career_record.coroutine(title="项目会议", summary="确认接口范围", runtime=_runtime())

    assert result == {"saved": False, "cancelled": True, "reason": "用户未确认保存"}
    assert _FakeRepository.calls == []


@pytest.mark.asyncio
async def test_career_record_confirmation_payload_is_explicit(monkeypatch):
    _patch_storage(monkeypatch)
    payloads = []
    monkeypatch.setattr(
        career,
        "interrupt",
        lambda payload: payloads.append(payload) or {"save_career_record": "confirm"},
    )

    await career.save_career_record.coroutine(title="项目会议", summary="确认接口范围", runtime=_runtime())

    question = payloads[0]["questions"][0]
    assert payloads[0]["source"] == "career_record_confirmation"
    assert question["question_id"] == "save_career_record"
    assert {option["value"] for option in question["options"]} == {"confirm", "cancel"}


def test_career_skills_are_registered_and_isolated_from_existing_domains():
    specs = {item.slug: item for item in BUILTIN_SKILLS}
    tools = {item.name for item in get_all_tool_instances()}
    assert {"career-work", "career-document", "career-planning"} <= specs.keys()
    assert set(specs["career-work"].tool_dependencies) <= tools
    assert specs["career-document"].skill_dependencies == ("career-work",)
    assert specs["career-planning"].skill_dependencies == ("career-work",)

    dependency_map = {item.slug: {"skills": list(item.skill_dependencies)} for item in BUILTIN_SKILLS}
    career_closure = expand_skill_closure(["career-document", "career-planning"], dependency_map)
    visual_closure = expand_skill_closure(["visual-research"], dependency_map)
    assert career_closure == ["career-document", "career-work", "career-planning"]
    assert "visual-research" not in career_closure
    assert "career-work" not in visual_closure


@pytest.mark.asyncio
async def test_career_tools_are_gated_to_career_skill(monkeypatch):
    monkeypatch.setattr(mcp_service, "get_enabled_mcp_tools", lambda _name: [])
    career_context = SimpleNamespace(
        tools=[],
        mcps=[],
        skills=["career-work"],
        _readable_skills=["career-work"],
        _runtime_skill_dependency_map={"career-work": {"tools": ["save_career_record", "list_career_records"]}},
    )
    visual_context = SimpleNamespace(
        tools=[],
        mcps=[],
        skills=["visual-observation"],
        _readable_skills=["visual-observation"],
        _runtime_skill_dependency_map={"visual-observation": {"tools": ["save_visual_observation"]}},
    )
    career_tools = {item.name for item in await resolve_configured_runtime_tools(career_context)}
    visual_tools = {item.name for item in await resolve_configured_runtime_tools(visual_context)}
    assert {"save_career_record", "list_career_records"} <= career_tools
    assert "save_career_record" not in visual_tools
