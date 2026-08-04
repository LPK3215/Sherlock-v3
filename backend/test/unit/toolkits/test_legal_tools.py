from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from yuxi.agents.skills.buildin import BUILTIN_SKILLS
from yuxi.agents.middlewares.skills import expand_skill_closure
from yuxi.agents.toolkits import legal
from yuxi.agents.toolkits.registry import get_all_tool_instances, get_extra_metadata


class _FakeSession:
    pass


class _FakeMatter:
    def __init__(self, matter_id: int = 11):
        self.matter_id = matter_id

    def to_dict(self) -> dict:
        return {"id": self.matter_id, "uid": "user-1"}


class _FakeRepository:
    calls: list[tuple[str, dict]] = []

    def __init__(self, _db):
        pass

    async def create_matter(self, **kwargs):
        self.calls.append(("create", kwargs))
        return _FakeMatter()

    async def list_matters(self, **kwargs):
        self.calls.append(("list", kwargs))
        return [_FakeMatter()]

    async def update_matter(self, **kwargs):
        self.calls.append(("update", kwargs))
        return _FakeMatter()

    async def delete_matter(self, **kwargs):
        self.calls.append(("delete", kwargs))
        return True


def _runtime(uid: str = "user-1"):
    return SimpleNamespace(context=SimpleNamespace(uid=uid))


@asynccontextmanager
async def _session_context():
    yield _FakeSession()


def _patch_legal_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepository.calls = []
    monkeypatch.setattr(legal, "LegalRepository", _FakeRepository)
    monkeypatch.setattr(legal.pg_manager, "get_async_session_context", _session_context)


def test_legal_tools_are_registered_with_metadata():
    names = {item.name for item in get_all_tool_instances()}

    assert {
        "save_legal_matter",
        "list_legal_matters",
        "update_legal_matter",
        "delete_legal_matter",
    } <= names
    assert get_extra_metadata("save_legal_matter").category == "legal"


@pytest.mark.asyncio
async def test_legal_tools_use_current_user_uid(monkeypatch: pytest.MonkeyPatch):
    _patch_legal_storage(monkeypatch)

    await legal.save_legal_matter.coroutine(title="合同争议", summary="用户确认的摘要", runtime=_runtime())
    await legal.list_legal_matters.coroutine(runtime=_runtime(), matter_type="contract", limit=5)
    await legal.update_legal_matter.coroutine(matter_id=11, runtime=_runtime(), status="closed")
    await legal.delete_legal_matter.coroutine(matter_id=11, runtime=_runtime())

    assert all(call[1]["uid"] == "user-1" for call in _FakeRepository.calls)
    assert _FakeRepository.calls[1][1]["limit"] == 5
    assert _FakeRepository.calls[2][1]["matter_id"] == 11


@pytest.mark.asyncio
async def test_save_legal_matter_rejects_blank_values(monkeypatch: pytest.MonkeyPatch):
    _patch_legal_storage(monkeypatch)

    with pytest.raises(ValueError, match="标题和摘要不能为空"):
        await legal.save_legal_matter.coroutine(title=" ", summary="摘要", runtime=_runtime())

    assert _FakeRepository.calls == []


def test_builtin_skills_have_registered_tool_and_skill_dependencies():
    tool_names = {item.name for item in get_all_tool_instances()}
    skill_slugs = {item.slug for item in BUILTIN_SKILLS}

    for spec in BUILTIN_SKILLS:
        assert set(spec.tool_dependencies) <= tool_names, spec.slug
        assert set(spec.skill_dependencies) <= skill_slugs, spec.slug


def test_two_domains_are_registered_without_cross_domain_dependencies():
    specs = {item.slug: item for item in BUILTIN_SKILLS}

    assert specs["junior-math-learning"].skill_dependencies == ("knowledge-base",)
    assert specs["legal-matter-analysis"].skill_dependencies == (
        "knowledge-base",
        "legal-contract-analysis",
        "legal-fact-organizer",
    )
    assert "save_wrong_question" in specs["junior-math-learning"].tool_dependencies
    assert "save_legal_matter" in specs["legal-matter-analysis"].tool_dependencies


def test_runtime_skill_closure_switches_between_domains_without_cross_contamination():
    dependency_map = {
        item.slug: {"skills": list(item.skill_dependencies)} for item in BUILTIN_SKILLS
    }

    student_closure = expand_skill_closure(["junior-math-learning"], dependency_map)
    legal_closure = expand_skill_closure(["legal-matter-analysis"], dependency_map)

    assert student_closure == ["junior-math-learning", "knowledge-base"]
    assert legal_closure == [
        "legal-matter-analysis",
        "knowledge-base",
        "legal-contract-analysis",
        "legal-fact-organizer",
    ]
    assert "legal-matter-analysis" not in student_closure
    assert "junior-math-learning" not in legal_closure
