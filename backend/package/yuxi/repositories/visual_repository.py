from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import VisualObservation


class VisualRepository:
    """视觉观察数据访问边界,所有查询都按用户 UID 隔离。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_observation(self, *, uid: str, values: dict) -> VisualObservation:
        item = VisualObservation(uid=uid, **values)
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def list_observations(
        self, *, uid: str, subject: str | None = None, limit: int = 20
    ) -> list[VisualObservation]:
        stmt = select(VisualObservation).where(VisualObservation.uid == uid)
        if subject:
            stmt = stmt.where(VisualObservation.subject == subject)
        stmt = stmt.order_by(VisualObservation.updated_at.desc(), VisualObservation.id.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
