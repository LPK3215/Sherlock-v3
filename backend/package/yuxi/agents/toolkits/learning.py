"""学生学习助手的业务工具。"""

from __future__ import annotations

from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, Field

from yuxi.agents.toolkits.registry import tool
from yuxi.repositories.learning_repository import LearningRepository
from yuxi.storage.postgres.manager import pg_manager


def _runtime_uid(runtime: ToolRuntime) -> str:
    uid = str(getattr(runtime.context, "uid", "") or "").strip()
    if not uid:
        raise ValueError("当前运行缺少用户身份")
    return uid


class SaveWrongQuestionInput(BaseModel):
    question: str = Field(description="题目原文或题目内容")
    student_answer: str | None = Field(default=None, description="学生作答内容")
    analysis: str | None = Field(default=None, description="错误原因或讲解摘要")
    grade: str | None = Field(default=None, description="年级,例如初一")
    subject: str = Field(default="数学", description="学科")
    knowledge_point: str | None = Field(default=None, description="知识点")


@tool(
    category="learning",
    tags=["学生", "错题", "数据库"],
    display_name="保存错题",
    description="将当前用户的错题和讲解摘要保存到学习记录中。用户明确要求保存后调用。",
    args_schema=SaveWrongQuestionInput,
)
async def save_wrong_question(
    question: str,
    runtime: ToolRuntime,
    student_answer: str | None = None,
    analysis: str | None = None,
    grade: str | None = None,
    subject: str = "数学",
    knowledge_point: str | None = None,
) -> dict:
    values = {
        "question": question.strip(),
        "student_answer": student_answer,
        "analysis": analysis,
        "grade": grade,
        "subject": subject.strip() or "数学",
        "knowledge_point": knowledge_point,
    }
    if not values["question"]:
        raise ValueError("题目不能为空")
    async with pg_manager.get_async_session_context() as db:
        item = await LearningRepository(db).create_wrong_question(uid=_runtime_uid(runtime), values=values)
    return {"saved": True, "wrong_question": item.to_dict()}


class ListWrongQuestionsInput(BaseModel):
    subject: str | None = Field(default=None, description="按学科筛选")
    knowledge_point: str | None = Field(default=None, description="按知识点筛选")
    review_status: str | None = Field(default=None, description="复习状态,例如 pending 或 reviewed")
    limit: int = Field(default=20, ge=1, le=100, description="最多返回条数")


@tool(
    category="learning",
    tags=["学生", "错题", "查询"],
    display_name="查询错题",
    description="查询当前用户自己的错题记录,支持按学科、知识点和复习状态筛选。",
    args_schema=ListWrongQuestionsInput,
)
async def list_wrong_questions(
    runtime: ToolRuntime,
    subject: str | None = None,
    knowledge_point: str | None = None,
    review_status: str | None = None,
    limit: int = 20,
) -> dict:
    async with pg_manager.get_async_session_context() as db:
        items = await LearningRepository(db).list_wrong_questions(
            uid=_runtime_uid(runtime),
            subject=subject,
            knowledge_point=knowledge_point,
            review_status=review_status,
            limit=limit,
        )
    return {"count": len(items), "wrong_questions": [item.to_dict() for item in items]}


class UpdateWrongQuestionInput(BaseModel):
    question_id: int = Field(description="错题记录 ID")
    review_status: str | None = Field(default=None, description="复习状态,例如 pending、reviewing、reviewed")
    analysis: str | None = Field(default=None, description="更新后的错误原因或讲解摘要")
    knowledge_point: str | None = Field(default=None, description="更新后的知识点")


@tool(
    category="learning",
    tags=["学生", "错题", "更新"],
    display_name="更新错题",
    description="更新当前用户自己的错题复习状态、讲解或知识点。执行前应确认用户确实要修改记录。",
    args_schema=UpdateWrongQuestionInput,
)
async def update_wrong_question(
    question_id: int,
    runtime: ToolRuntime,
    review_status: str | None = None,
    analysis: str | None = None,
    knowledge_point: str | None = None,
) -> dict:
    values = {
        key: value
        for key, value in {
            "review_status": review_status,
            "analysis": analysis,
            "knowledge_point": knowledge_point,
        }.items()
        if value is not None
    }
    if not values:
        raise ValueError("至少提供一个要更新的字段")
    async with pg_manager.get_async_session_context() as db:
        item = await LearningRepository(db).update_wrong_question(
            uid=_runtime_uid(runtime), question_id=question_id, values=values
        )
    if item is None:
        raise ValueError("错题不存在或不属于当前用户")
    return {"updated": True, "wrong_question": item.to_dict()}


class DeleteWrongQuestionInput(BaseModel):
    question_id: int = Field(description="错题记录 ID")


@tool(
    category="learning",
    tags=["学生", "错题", "删除"],
    display_name="删除错题",
    description="删除当前用户自己的错题记录。必须在用户明确确认删除后调用。",
    args_schema=DeleteWrongQuestionInput,
)
async def delete_wrong_question(question_id: int, runtime: ToolRuntime) -> dict:
    async with pg_manager.get_async_session_context() as db:
        deleted = await LearningRepository(db).delete_wrong_question(uid=_runtime_uid(runtime), question_id=question_id)
    if not deleted:
        raise ValueError("错题不存在或不属于当前用户")
    return {"deleted": True, "question_id": question_id}
