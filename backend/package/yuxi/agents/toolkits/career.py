"""职场与个人工作领域的确认式记录工具。"""

from __future__ import annotations

from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from yuxi.agents.toolkits.registry import tool
from yuxi.repositories.career_repository import CareerRepository
from yuxi.storage.postgres.manager import pg_manager
from yuxi.agents.toolkits.runtime import get_runtime_uid


class SaveCareerRecordInput(BaseModel):
    title: str = Field(description="工作或职业记录标题")
    summary: str = Field(description="整理后的事实、目标或会议摘要")
    record_type: str = Field(
        default="work_item", description="类型,例如 work_item、meeting、interview、application 或 plan"
    )
    action_items: str | None = Field(default=None, description="待办事项或下一步行动")
    status: str = Field(default="open", description="状态,例如 open、in_progress、done 或 archived")
    due_date: str | None = Field(default=None, description="用户提供的截止日期或时间描述")
    source_reference: str | None = Field(default=None, description="来源文档、会议或对话引用")
    user_note: str | None = Field(default=None, description="用户备注")


@tool(
    category="career",
    tags=["职场", "职业记录", "数据库"],
    display_name="保存职业记录",
    description="将用户明确确认的工作或职业结构化摘要保存到当前用户记录。未经确认不得调用,不自动保存整段对话或原始文件。",
    args_schema=SaveCareerRecordInput,
)
async def save_career_record(
    title: str,
    summary: str,
    runtime: ToolRuntime,
    record_type: str = "work_item",
    action_items: str | None = None,
    status: str = "open",
    due_date: str | None = None,
    source_reference: str | None = None,
    user_note: str | None = None,
) -> dict:
    values = {
        "title": title.strip(),
        "summary": summary.strip(),
        "record_type": record_type.strip() or "work_item",
        "action_items": action_items.strip() if action_items else None,
        "status": status.strip() or "open",
        "due_date": due_date.strip() if due_date else None,
        "source_reference": source_reference.strip() if source_reference else None,
        "user_note": user_note.strip() if user_note else None,
    }
    if not values["title"] or not values["summary"]:
        raise ValueError("职业记录标题和摘要不能为空")

    confirmation = interrupt(
        {
            "source": "career_record_confirmation",
            "questions": [
                {
                    "question_id": "save_career_record",
                    "question": f'确认保存职业记录“{values["title"]}”吗？',
                    "options": [
                        {"label": "确认保存", "value": "confirm"},
                        {"label": "取消保存", "value": "cancel"},
                    ],
                    "multi_select": False,
                    "allow_other": False,
                }
            ],
        }
    )
    answer = confirmation.get("save_career_record") if isinstance(confirmation, dict) else confirmation
    if answer != "confirm":
        return {"saved": False, "cancelled": True, "reason": "用户未确认保存"}

    async with pg_manager.get_async_session_context() as db:
        item = await CareerRepository(db).create_record(uid=get_runtime_uid(runtime), values=values)
    return {"saved": True, "career_record": item.to_dict()}


class ListCareerRecordsInput(BaseModel):
    record_type: str | None = Field(default=None, description="按记录类型筛选")
    status: str | None = Field(default=None, description="按状态筛选")
    limit: int = Field(default=20, ge=1, le=100, description="最多返回条数")


@tool(
    category="career",
    tags=["职场", "职业记录", "查询"],
    display_name="查询职业记录",
    description="查询当前用户自己的工作与职业记录,按用户身份隔离。",
    args_schema=ListCareerRecordsInput,
)
async def list_career_records(
    runtime: ToolRuntime,
    record_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> dict:
    async with pg_manager.get_async_session_context() as db:
        items = await CareerRepository(db).list_records(
            uid=get_runtime_uid(runtime), record_type=record_type, status=status, limit=limit
        )
    return {"count": len(items), "career_records": [item.to_dict() for item in items]}
