"""视觉观察领域的确认式记录工具。"""

from __future__ import annotations

from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, Field

from yuxi.agents.toolkits.registry import tool
from yuxi.repositories.visual_repository import VisualRepository
from yuxi.storage.postgres.manager import pg_manager


def _runtime_uid(runtime: ToolRuntime) -> str:
    uid = str(getattr(runtime.context, "uid", "") or "").strip()
    if not uid:
        raise ValueError("当前运行缺少用户身份")
    return uid


class SaveVisualObservationInput(BaseModel):
    title: str = Field(description="这次观察的标题")
    subject: str = Field(description="观察对象,例如植物、动物、设备或物品")
    direct_observation: str = Field(description="从当前图片、视频帧或屏幕中直接观察到的内容")
    candidate_identification: str | None = Field(default=None, description="模型给出的候选识别,不代表专业鉴定")
    research_summary: str | None = Field(default=None, description="检索或知识库核验摘要")
    user_question: str | None = Field(default=None, description="用户当时的问题")
    confidence: str | None = Field(default=None, description="低、中或高等置信度说明")
    location: str | None = Field(default=None, description="用户提供的观察地点")
    source_reference: str | None = Field(default=None, description="来源链接或对话引用,不填写原图内容")
    user_note: str | None = Field(default=None, description="用户备注")


@tool(
    category="visual",
    tags=["视觉", "观察记录", "数据库"],
    display_name="保存视觉观察",
    description="将用户明确确认的视觉观察结构化摘要保存到当前用户记录。普通识别和观察未经确认不得调用,不保存原始图片或视频帧。",
    args_schema=SaveVisualObservationInput,
)
async def save_visual_observation(
    title: str,
    subject: str,
    direct_observation: str,
    runtime: ToolRuntime,
    candidate_identification: str | None = None,
    research_summary: str | None = None,
    user_question: str | None = None,
    confidence: str | None = None,
    location: str | None = None,
    source_reference: str | None = None,
    user_note: str | None = None,
) -> dict:
    values = {
        "title": title.strip(),
        "subject": subject.strip(),
        "direct_observation": direct_observation.strip(),
        "candidate_identification": candidate_identification.strip() if candidate_identification else None,
        "research_summary": research_summary.strip() if research_summary else None,
        "user_question": user_question.strip() if user_question else None,
        "confidence": confidence.strip() if confidence else None,
        "location": location.strip() if location else None,
        "source_reference": source_reference.strip() if source_reference else None,
        "user_note": user_note.strip() if user_note else None,
    }
    if not values["title"] or not values["subject"] or not values["direct_observation"]:
        raise ValueError("视觉观察标题、对象和直接观察内容不能为空")
    async with pg_manager.get_async_session_context() as db:
        item = await VisualRepository(db).create_observation(uid=_runtime_uid(runtime), values=values)
    return {"saved": True, "visual_observation": item.to_dict()}


class ListVisualObservationsInput(BaseModel):
    subject: str | None = Field(default=None, description="按观察对象筛选")
    limit: int = Field(default=20, ge=1, le=100, description="最多返回条数")


@tool(
    category="visual",
    tags=["视觉", "观察记录", "查询"],
    display_name="查询视觉观察",
    description="查询当前用户自己的视觉观察摘要,按用户身份隔离,不返回原始图片或视频帧。",
    args_schema=ListVisualObservationsInput,
)
async def list_visual_observations(
    runtime: ToolRuntime, subject: str | None = None, limit: int = 20
) -> dict:
    async with pg_manager.get_async_session_context() as db:
        items = await VisualRepository(db).list_observations(
            uid=_runtime_uid(runtime), subject=subject, limit=limit
        )
    return {"count": len(items), "visual_observations": [item.to_dict() for item in items]}
