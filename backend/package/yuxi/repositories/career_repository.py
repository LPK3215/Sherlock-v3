from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import CareerRecord


class CareerRepository:
    """工作与职业记录访问边界,所有查询都按用户 UID 隔离。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_record(self, *, uid: str, values: dict) -> CareerRecord:
        item = CareerRecord(uid=uid, **values)
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def list_records(
        self,
        *,
        uid: str,
        record_type: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[CareerRecord]:
        stmt = select(CareerRecord).where(CareerRecord.uid == uid)
        if record_type:
            stmt = stmt.where(CareerRecord.record_type == record_type)
        if status:
            stmt = stmt.where(CareerRecord.status == status)
        stmt = stmt.order_by(CareerRecord.updated_at.desc(), CareerRecord.id.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
