from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from yuxi.agents.toolkits import learning
from yuxi.agents.toolkits.registry import get_all_tool_instances, get_extra_metadata
from yuxi.agents.skills.buildin import BUILTIN_SKILLS


class _FakeSession:
    pass


class _FakeItem:
    def __init__(self, item_id: int = 7):
        self.item_id = item_id

    def to_dict(self) -> dict:
        return {"id": self.item_id, "uid": "student-1"}


class _FakeRepository:
    calls: list[tuple[str, dict]] = []

    def __init__(self, _db):
        pass

    async def create_wrong_question(self, **kwargs):
        self.calls.append(("create", kwargs))
        return _FakeItem()

    async def list_wrong_questions(self, **kwargs):
        self.calls.append(("list", kwargs))
        return [_FakeItem()]

    async def update_wrong_question(self, **kwargs):
        self.calls.append(("update", kwargs))
        return _FakeItem()

    async def delete_wrong_question(self, **kwargs):
        self.calls.append(("delete", kwargs))
        return True


def _runtime(uid: str = "student-1"):
    return SimpleNamespace(context=SimpleNamespace(uid=uid))


@asynccontextmanager
async def _session_context():
    yield _FakeSession()


def _patch_learning_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepository.calls = []
    monkeypatch.setattr(learning, "LearningRepository", _FakeRepository)
    monkeypatch.setattr(learning.pg_manager, "get_async_session_context", _session_context)


def test_learning_tools_are_registered_with_metadata():
    names = {item.name for item in get_all_tool_instances()}

    assert {
        "save_wrong_question",
        "list_wrong_questions",
        "update_wrong_question",
        "delete_wrong_question",
    } <= names
    assert get_extra_metadata("save_wrong_question").category == "learning"


@pytest.mark.asyncio
async def test_save_wrong_question_rejects_blank_question(monkeypatch: pytest.MonkeyPatch):
    _patch_learning_storage(monkeypatch)

    with pytest.raises(ValueError, match="题目不能为空"):
        await learning.save_wrong_question.coroutine(question="  ", runtime=_runtime())

    assert _FakeRepository.calls == []


@pytest.mark.asyncio
async def test_learning_tools_use_current_user_uid(monkeypatch: pytest.MonkeyPatch):
    _patch_learning_storage(monkeypatch)

    await learning.save_wrong_question.coroutine(question="2x=4", runtime=_runtime())
    await learning.list_wrong_questions.coroutine(runtime=_runtime(), subject="数学", limit=5)
    await learning.update_wrong_question.coroutine(question_id=7, runtime=_runtime(), review_status="reviewed")
    await learning.delete_wrong_question.coroutine(question_id=7, runtime=_runtime())

    assert all(call[1]["uid"] == "student-1" for call in _FakeRepository.calls)
    assert _FakeRepository.calls[1][1]["limit"] == 5
    assert _FakeRepository.calls[2][1]["question_id"] == 7


@pytest.mark.asyncio
async def test_update_wrong_question_requires_a_field(monkeypatch: pytest.MonkeyPatch):
    _patch_learning_storage(monkeypatch)

    with pytest.raises(ValueError, match="至少提供一个"):
        await learning.update_wrong_question.coroutine(question_id=7, runtime=_runtime())


def test_student_problem_skill_declares_learning_and_knowledge_dependencies():
    spec = next(item for item in BUILTIN_SKILLS if item.slug == "junior-math-learning")

    assert "save_wrong_question" in spec.tool_dependencies
    assert "query_kb" in spec.tool_dependencies
    assert spec.skill_dependencies == ("knowledge-base",)

    skill_text = (spec.source_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "通用学生拍题助手" in skill_text
    assert "不要因为用户没有上传教材或题库就拒绝解题" in skill_text
    assert "只有用户要求依据某本教材" in skill_text
    assert "不要自动记录所有题目" in skill_text
    assert "只能初中数学" not in skill_text
