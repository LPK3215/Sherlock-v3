from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from yuxi.agents.middlewares.skills import expand_skill_closure
from yuxi.agents.skills.buildin import BUILTIN_SKILLS
from yuxi.agents.mcp import service as mcp_service
from yuxi.agents.toolkits import visual
from yuxi.agents.toolkits.registry import get_all_tool_instances, get_extra_metadata
from yuxi.agents.toolkits.service import resolve_configured_runtime_tools


class _FakeObservation:
    def to_dict(self):
        return {"id": 3, "uid": "user-1", "subject": "植物"}


class _FakeRepository:
    calls = []

    def __init__(self, _db):
        pass

    async def create_observation(self, **kwargs):
        self.calls.append(("create", kwargs))
        return _FakeObservation()

    async def list_observations(self, **kwargs):
        self.calls.append(("list", kwargs))
        return [_FakeObservation()]


def _runtime(uid="user-1"):
    return SimpleNamespace(context=SimpleNamespace(uid=uid))


@asynccontextmanager
async def _session_context():
    yield object()


def _patch_storage(monkeypatch):
    _FakeRepository.calls = []
    monkeypatch.setattr(visual, "VisualRepository", _FakeRepository)
    monkeypatch.setattr(visual.pg_manager, "get_async_session_context", _session_context)


def test_visual_tools_are_registered_and_categorized():
    names = {item.name for item in get_all_tool_instances()}
    assert {"save_visual_observation", "list_visual_observations"} <= names
    assert get_extra_metadata("save_visual_observation").category == "visual"


@pytest.mark.asyncio
async def test_visual_tools_use_current_uid_and_validate_required_fields(monkeypatch):
    _patch_storage(monkeypatch)
    monkeypatch.setattr(visual, "interrupt", lambda payload: {payload["questions"][0]["question_id"]: "confirm"})

    with pytest.raises(ValueError, match="标题、对象和直接观察内容不能为空"):
        await visual.save_visual_observation.coroutine(
            title=" ", subject="植物", direct_observation="叶片", runtime=_runtime()
        )
    await visual.save_visual_observation.coroutine(
        title="窗台观察", subject="植物", direct_observation="绿色叶片", runtime=_runtime()
    )
    await visual.list_visual_observations.coroutine(runtime=_runtime("user-2"), subject="植物", limit=5)

    assert _FakeRepository.calls[0][1]["uid"] == "user-1"
    assert _FakeRepository.calls[1][1] == {"uid": "user-2", "subject": "植物", "limit": 5}


@pytest.mark.asyncio
async def test_visual_save_does_not_persist_without_confirmation(monkeypatch):
    _patch_storage(monkeypatch)
    monkeypatch.setattr(visual, "interrupt", lambda _payload: {"save_visual_observation": "cancel"})

    result = await visual.save_visual_observation.coroutine(
        title="窗台观察", subject="植物", direct_observation="绿色叶片", runtime=_runtime()
    )

    assert result["saved"] is False
    assert result["cancelled"] is True
    assert _FakeRepository.calls == []


def test_visual_skills_and_three_domain_closure_are_registered():
    specs = {item.slug: item for item in BUILTIN_SKILLS}
    tools = {item.name for item in get_all_tool_instances()}
    assert {"visual-observation", "visual-identification", "visual-research"} <= specs.keys()
    assert set(specs["visual-observation"].tool_dependencies) <= tools
    assert specs["visual-identification"].skill_dependencies == ("visual-observation",)
    assert specs["visual-research"].skill_dependencies == ("visual-observation", "knowledge-base")

    dependency_map = {item.slug: {"skills": list(item.skill_dependencies)} for item in BUILTIN_SKILLS}
    visual_closure = expand_skill_closure(["visual-research"], dependency_map)
    student_closure = expand_skill_closure(["junior-math-learning"], dependency_map)
    legal_closure = expand_skill_closure(["legal-matter-analysis"], dependency_map)
    assert visual_closure == ["visual-research", "visual-observation", "knowledge-base"]
    assert "visual-research" not in student_closure + legal_closure
    assert "junior-math-learning" not in visual_closure


@pytest.mark.asyncio
async def test_runtime_tools_keep_visual_domain_gated(monkeypatch):
    monkeypatch.setattr(mcp_service, "get_enabled_mcp_tools", lambda _name: [])
    visual_context = SimpleNamespace(
        tools=[],
        mcps=[],
        skills=["visual-observation"],
        _readable_skills=["visual-observation"],
        _runtime_skill_dependency_map={
            "visual-observation": {"tools": ["save_visual_observation", "list_visual_observations"]}
        },
    )
    student_context = SimpleNamespace(
        tools=[],
        mcps=[],
        skills=["junior-math-learning"],
        _readable_skills=["junior-math-learning"],
        _runtime_skill_dependency_map={"junior-math-learning": {"tools": ["save_wrong_question"]}},
    )

    visual_tools = {item.name for item in await resolve_configured_runtime_tools(visual_context)}
    student_tools = {item.name for item in await resolve_configured_runtime_tools(student_context)}
    assert {"save_visual_observation", "list_visual_observations"} <= visual_tools
    assert "save_visual_observation" not in student_tools
