"""生成测试用 access token，输出到 stdout。"""

import asyncio
import os
from datetime import timedelta

import asyncpg
from yuxi.utils.auth_utils import AuthUtils


async def main():
    dsn = os.getenv("POSTGRES_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/yuxi").replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn)
    user_id = await conn.fetchval(
        "SELECT id FROM users WHERE role = 'superadmin' AND is_deleted = 0 AND department_id IS NOT NULL ORDER BY id LIMIT 1"
    )
    await conn.close()
    if not user_id:
        raise SystemExit("No superadmin user found")
    token = AuthUtils.create_access_token({"sub": str(user_id)}, expires_delta=timedelta(hours=2))
    print(token)


asyncio.run(main())
