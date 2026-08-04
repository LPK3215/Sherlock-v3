from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import LearningWrongQuestion
from yuxi.utils.datetime_utils import utc_now_naive


class LearningRepository:
    """学生学习业务数据访问边界。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_wrong_question(self, *, uid: str, values: dict) -> LearningWrongQuestion:
        item = LearningWrongQuestion(uid=uid, **values)
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def list_wrong_questions(
        self,
        *,
        uid: str,
        subject: str | None = None,
        knowledge_point: str | None = None,
        review_status: str | None = None,
        limit: int = 20,
    ) -> list[LearningWrongQuestion]:
        stmt = select(LearningWrongQuestion).where(LearningWrongQuestion.uid == uid)
        if subject:
            stmt = stmt.where(LearningWrongQuestion.subject == subject)
        if knowledge_point:
            stmt = stmt.where(LearningWrongQuestion.knowledge_point == knowledge_point)
        if review_status:
            stmt = stmt.where(LearningWrongQuestion.review_status == review_status)
        stmt = stmt.order_by(LearningWrongQuestion.updated_at.desc(), LearningWrongQuestion.id.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_wrong_question(self, *, uid: str, question_id: int, values: dict) -> LearningWrongQuestion | None:
        item = await self.db.scalar(
            select(LearningWrongQuestion).where(
                LearningWrongQuestion.id == question_id,
                LearningWrongQuestion.uid == uid,
            )
        )
        if item is None:
            return None
        for key, value in values.items():
            setattr(item, key, value)
        item.updated_at = utc_now_naive()
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def delete_wrong_question(self, *, uid: str, question_id: int) -> bool:
        result = await self.db.execute(
            delete(LearningWrongQuestion).where(
                LearningWrongQuestion.id == question_id,
                LearningWrongQuestion.uid == uid,
            )
        )
        await self.db.commit()
        return bool(result.rowcount)
