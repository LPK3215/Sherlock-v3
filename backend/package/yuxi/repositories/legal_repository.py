from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import LegalMatter
from yuxi.utils.datetime_utils import utc_now_naive


class LegalRepository:
    """法律事务数据访问边界,所有查询都按用户 UID 隔离。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_matter(self, *, uid: str, values: dict) -> LegalMatter:
        item = LegalMatter(uid=uid, **values)
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def list_matters(
        self, *, uid: str, matter_type: str | None = None, status: str | None = None, limit: int = 20
    ) -> list[LegalMatter]:
        stmt = select(LegalMatter).where(LegalMatter.uid == uid)
        if matter_type:
            stmt = stmt.where(LegalMatter.matter_type == matter_type)
        if status:
            stmt = stmt.where(LegalMatter.status == status)
        stmt = stmt.order_by(LegalMatter.updated_at.desc(), LegalMatter.id.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_matter(self, *, uid: str, matter_id: int, values: dict) -> LegalMatter | None:
        item = await self.db.scalar(
            select(LegalMatter).where(LegalMatter.id == matter_id, LegalMatter.uid == uid)
        )
        if item is None:
            return None
        for key, value in values.items():
            setattr(item, key, value)
        item.updated_at = utc_now_naive()
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def delete_matter(self, *, uid: str, matter_id: int) -> bool:
        result = await self.db.execute(
            delete(LegalMatter).where(LegalMatter.id == matter_id, LegalMatter.uid == uid)
        )
        await self.db.commit()
        return bool(result.rowcount)
