"""Tools that read media from an active Sherlock realtime session."""

from __future__ import annotations

import os
from typing import Literal

import httpx
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema

from yuxi.agents.toolkits.registry import tool


class CaptureLiveFrameInput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    runtime: SkipJsonSchema[ToolRuntime]


@tool(
    category="realtime",
    tags=["实时", "摄像头", "视觉"],
    display_name="查看实时摄像头",
    description="获取用户当前摄像头的一张最新画面。仅当用户正在实时通话且问题需要视觉信息时调用。",
    args_schema=CaptureLiveFrameInput,
)
async def capture_live_camera(
    runtime: ToolRuntime,
) -> Command:
    return await _capture_live_frame("camera", runtime, str(runtime.tool_call_id or ""))


@tool(
    category="realtime",
    tags=["实时", "屏幕", "视觉"],
    display_name="查看实时屏幕",
    description="获取用户当前共享屏幕的一张最新画面。仅当用户正在实时通话且问题涉及屏幕内容时调用。",
    args_schema=CaptureLiveFrameInput,
)
async def capture_live_screen(
    runtime: ToolRuntime,
) -> Command:
    return await _capture_live_frame("screen", runtime, str(runtime.tool_call_id or ""))


async def _capture_live_frame(
    source: Literal["camera", "screen"],
    runtime: ToolRuntime,
    tool_call_id: str,
) -> Command:
    session_id = str(getattr(runtime.context, "realtime_session_id", "") or "").strip()
    uid = str(getattr(runtime.context, "uid", "") or "").strip()
    if not session_id or not uid:
        return _tool_error(tool_call_id, "当前运行不属于有效的实时会话")

    gateway_url = os.getenv("REALTIME_GATEWAY_INTERNAL_URL", "http://realtime-gateway:7860").rstrip("/")
    token = os.getenv("REALTIME_GATEWAY_INTERNAL_TOKEN")
    if not token:
        return _tool_error(tool_call_id, "实时媒体服务未配置内部凭证")

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{gateway_url}/internal/realtime/sessions/{session_id}/frames/capture",
                headers={"Authorization": f"Bearer {token}", "X-Yuxi-Uid": uid},
                json={"source": source, "wait_fresh_ms": 3000},
            )
        response.raise_for_status()
        payload = response.json()
        image_base64 = payload.get("data_base64")
        mime_type = payload.get("mime_type") or "image/jpeg"
        if not image_base64:
            return _tool_error(tool_call_id, "实时媒体服务没有返回图片")
    except (httpx.HTTPError, ValueError) as exc:
        return _tool_error(tool_call_id, f"抓取实时画面失败: {exc}")

    source_label = "摄像头" if source == "camera" else "共享屏幕"
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=[
                        {"type": "text", "text": f"这是用户当前的{source_label}画面。"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                        },
                    ],
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )


def _tool_error(tool_call_id: str, message: str) -> Command:
    return Command(update={"messages": [ToolMessage(content=f"Error: {message}", tool_call_id=tool_call_id)]})
