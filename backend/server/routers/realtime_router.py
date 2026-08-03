"""Realtime session 端点：将 Yuxi access_token 存入 Redis，返回 session_id。

realtime-client 的 /api/start 路由调用此端点，只把 session_id 传给 Gateway，
避免 access_token 在 Gateway 请求体中明文传递。
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_required_user
from yuxi.storage.redis import sync_redis_client
from yuxi.utils.logging_config import logger

router = APIRouter(prefix="/realtime", tags=["realtime"])

SESSION_KEY_PREFIX = "yuxi:realtime_session:"
SESSION_TTL_SECONDS = 7200


class RealtimeSessionCreate(BaseModel):
    agent_slug: str
    thread_id: str | None = None


class RealtimeSessionResponse(BaseModel):
    session_id: str


@router.post("/session", response_model=RealtimeSessionResponse)
async def create_realtime_session(
    payload: RealtimeSessionCreate,
    user=Depends(get_required_user),
) -> RealtimeSessionResponse:
    """将当前用户的 access_token 存入 Redis，返回 session_id 供 Gateway 查询。"""
    session_id = f"rt-{uuid.uuid4()}"
    session_data: dict[str, Any] = {
        "access_token": user.access_token,
        "agent_slug": payload.agent_slug,
        "thread_id": payload.thread_id,
    }
    try:
        with sync_redis_client() as redis_client:
            redis_client.setex(
                f"{SESSION_KEY_PREFIX}{session_id}",
                SESSION_TTL_SECONDS,
                json.dumps(session_data, ensure_ascii=False),
            )
    except Exception as e:
        logger.error(f"Failed to store realtime session in Redis: {e}")
        raise HTTPException(status_code=500, detail="创建实时会话凭证失败") from e

    return RealtimeSessionResponse(session_id=session_id)
