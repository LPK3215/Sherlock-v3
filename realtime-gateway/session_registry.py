"""Redis Session Registry：Gateway 通过 session_id 查询 Yuxi access token。

存储格式：
  key: yuxi:realtime_session:{session_id}
  value: {"access_token": "...", "agent_slug": "...", "thread_id": "..."}
  TTL: 2 小时

写入方：realtime-client 的 /api/start 路由（服务端）或 Yuxi API。
读取方：Gateway 的 YuxiSessionConfig.from_runner_body。
"""

from __future__ import annotations

import json
import os
from typing import Any

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SESSION_KEY_PREFIX = "yuxi:realtime_session:"
SESSION_TTL_SECONDS = 7200


def _get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def store_session(session_id: str, data: dict[str, Any]) -> None:
    """将 session 凭证写入 Redis。"""
    client = _get_redis()
    client.setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        SESSION_TTL_SECONDS,
        json.dumps(data, ensure_ascii=False),
    )


def load_session(session_id: str) -> dict[str, Any] | None:
    """通过 session_id 读取 session 凭证，不存在返回 None。"""
    client = _get_redis()
    raw = client.get(f"{SESSION_KEY_PREFIX}{session_id}")
    if not raw:
        return None
    return json.loads(raw)


def delete_session(session_id: str) -> None:
    """主动删除 session。"""
    client = _get_redis()
    client.delete(f"{SESSION_KEY_PREFIX}{session_id}")
