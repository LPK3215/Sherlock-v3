"""重建模型缓存，使 input_modalities 字段生效。"""

import asyncio

from sqlalchemy import select
from yuxi.models.providers.cache import model_cache
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import ModelProvider


async def rebuild():
    await pg_manager.initialize()
    async with pg_manager.get_async_session_context() as s:
        result = await s.execute(select(ModelProvider))
        providers = result.scalars().all()
        model_cache.rebuild(providers)
        print("Cache rebuilt")
    await pg_manager.close()


asyncio.run(rebuild())
