"""法律事务领域的结构化记录工具。"""

from __future__ import annotations

from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from yuxi.agents.toolkits.registry import tool
from yuxi.repositories.legal_repository import LegalRepository
from yuxi.storage.postgres.manager import pg_manager


def _runtime_uid(runtime: ToolRuntime) -> str:
    uid = str(getattr(runtime.context, "uid", "") or "").strip()
    if not uid:
        raise ValueError("当前运行缺少用户身份")
    return uid


class SaveLegalMatterInput(BaseModel):
    title: str = Field(description="法律事务标题")
    matter_type: str = Field(default="general", description="事务类型,例如合同、劳动、消费或其他")
    summary: str = Field(description="用户确认要保存的事实或分析摘要")
    risk_summary: str | None = Field(default=None, description="风险摘要")
    next_actions: str | None = Field(default=None, description="后续事项")


@tool(
    category="legal",
    tags=["法律", "事务记录", "数据库"],
    display_name="保存法律事务",
    description="将用户明确确认的法律事务摘要保存到当前用户的记录中。未经确认不得调用。",
    args_schema=SaveLegalMatterInput,
)
async def save_legal_matter(
    title: str,
    summary: str,
    runtime: ToolRuntime,
    matter_type: str = "general",
    risk_summary: str | None = None,
    next_actions: str | None = None,
) -> dict:
    values = {
        "title": title.strip(),
        "matter_type": matter_type.strip() or "general",
        "summary": summary.strip(),
        "risk_summary": risk_summary,
        "next_actions": next_actions,
    }
    if not values["title"] or not values["summary"]:
        raise ValueError("法律事务标题和摘要不能为空")
    confirmation = interrupt(
        {
            "source": "legal_matter_confirmation",
            "questions": [{
                "question_id": "save_legal_matter",
                "question": f'确认保存法律事务“{values["title"]}”吗?',
                "options": [{"label": "确认执行", "value": "confirm"}, {"label": "取消执行", "value": "cancel"}],
                "multi_select": False,
                "allow_other": False,
            }],
        }
    )
    answer = confirmation.get("save_legal_matter") if isinstance(confirmation, dict) else confirmation
    if answer != "confirm":
        return {"saved": False, "cancelled": True, "reason": "用户未确认保存"}
    async with pg_manager.get_async_session_context() as db:
        item = await LegalRepository(db).create_matter(uid=_runtime_uid(runtime), values=values)
    return {"saved": True, "legal_matter": item.to_dict()}


class ListLegalMattersInput(BaseModel):
    matter_type: str | None = Field(default=None, description="按事务类型筛选")
    status: str | None = Field(default=None, description="按事务状态筛选")
    limit: int = Field(default=20, ge=1, le=100, description="最多返回条数")


@tool(
    category="legal",
    tags=["法律", "事务记录", "查询"],
    display_name="查询法律事务",
    description="查询当前用户自己的法律事务记录,支持按类型和状态筛选。",
    args_schema=ListLegalMattersInput,
)
async def list_legal_matters(
    runtime: ToolRuntime,
    matter_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> dict:
    async with pg_manager.get_async_session_context() as db:
        items = await LegalRepository(db).list_matters(
            uid=_runtime_uid(runtime), matter_type=matter_type, status=status, limit=limit
        )
    return {"count": len(items), "legal_matters": [item.to_dict() for item in items]}


class UpdateLegalMatterInput(BaseModel):
    matter_id: int = Field(description="法律事务记录 ID")
    title: str | None = Field(default=None, description="更新后的标题")
    summary: str | None = Field(default=None, description="更新后的摘要")
    risk_summary: str | None = Field(default=None, description="更新后的风险摘要")
    next_actions: str | None = Field(default=None, description="更新后的后续事项")
    status: str | None = Field(default=None, description="状态,例如 active、closed")


@tool(
    category="legal",
    tags=["法律", "事务记录", "更新"],
    display_name="更新法律事务",
    description="更新当前用户自己的法律事务记录。执行前必须确认具体修改内容。",
    args_schema=UpdateLegalMatterInput,
)
async def update_legal_matter(
    matter_id: int,
    runtime: ToolRuntime,
    title: str | None = None,
    summary: str | None = None,
    risk_summary: str | None = None,
    next_actions: str | None = None,
    status: str | None = None,
) -> dict:
    values = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in {
            "title": title,
            "summary": summary,
            "risk_summary": risk_summary,
            "next_actions": next_actions,
            "status": status,
        }.items()
        if value is not None
    }
    if not values:
        raise ValueError("至少提供一个要更新的字段")
    confirmation = interrupt(
        {
            "source": "legal_matter_confirmation",
            "questions": [{
                "question_id": "update_legal_matter",
                "question": f"确认修改法律事务记录 {matter_id} 吗?",
                "options": [{"label": "确认执行", "value": "confirm"}, {"label": "取消执行", "value": "cancel"}],
                "multi_select": False,
                "allow_other": False,
            }],
        }
    )
    answer = confirmation.get("update_legal_matter") if isinstance(confirmation, dict) else confirmation
    if answer != "confirm":
        return {"updated": False, "cancelled": True, "reason": "用户未确认修改"}
    async with pg_manager.get_async_session_context() as db:
        item = await LegalRepository(db).update_matter(
            uid=_runtime_uid(runtime), matter_id=matter_id, values=values
        )
    if item is None:
        raise ValueError("法律事务不存在或不属于当前用户")
    return {"updated": True, "legal_matter": item.to_dict()}


class DeleteLegalMatterInput(BaseModel):
    matter_id: int = Field(description="法律事务记录 ID")


@tool(
    category="legal",
    tags=["法律", "事务记录", "删除"],
    display_name="删除法律事务",
    description="删除当前用户自己的法律事务记录。必须在用户明确确认删除后调用。",
    args_schema=DeleteLegalMatterInput,
)
async def delete_legal_matter(matter_id: int, runtime: ToolRuntime) -> dict:
    confirmation = interrupt(
        {
            "source": "legal_matter_confirmation",
            "questions": [{
                "question_id": "delete_legal_matter",
                "question": f"确认删除法律事务记录 {matter_id} 吗?",
                "options": [{"label": "确认执行", "value": "confirm"}, {"label": "取消执行", "value": "cancel"}],
                "multi_select": False,
                "allow_other": False,
            }],
        }
    )
    answer = confirmation.get("delete_legal_matter") if isinstance(confirmation, dict) else confirmation
    if answer != "confirm":
        return {"deleted": False, "cancelled": True, "reason": "用户未确认删除"}
    async with pg_manager.get_async_session_context() as db:
        deleted = await LegalRepository(db).delete_matter(uid=_runtime_uid(runtime), matter_id=matter_id)
    if not deleted:
        raise ValueError("法律事务不存在或不属于当前用户")
    return {"deleted": True, "matter_id": matter_id}
