from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.repositories.career_repository import CareerRepository
from yuxi.storage.postgres.models_business import Base

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


@pytest_asyncio.fixture()
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def test_career_records_are_isolated_and_filterable(session):
    repo = CareerRepository(session)
    await repo.create_record(
        uid="user-a",
        values={"title": "会议", "summary": "确认范围", "record_type": "meeting", "status": "open"},
    )
    await repo.create_record(
        uid="user-a",
        values={"title": "简历", "summary": "补充项目", "record_type": "application", "status": "done"},
    )
    await repo.create_record(
        uid="user-b",
        values={"title": "他人的记录", "summary": "不可见", "record_type": "meeting", "status": "open"},
    )

    meetings = await repo.list_records(uid="user-a", record_type="meeting", status="open")
    assert [item.title for item in meetings] == ["会议"]
    assert await repo.list_records(uid="user-a", record_type="meeting", limit=1)
    assert await repo.list_records(uid="user-b")
    assert all(item.uid == "user-b" for item in await repo.list_records(uid="user-b"))


async def test_career_records_respect_limit_and_descending_update_order(session):
    repo = CareerRepository(session)
    for index in range(3):
        await repo.create_record(
            uid="user-a",
            values={"title": f"事项 {index}", "summary": "摘要", "record_type": "work_item", "status": "open"},
        )

    items = await repo.list_records(uid="user-a", limit=2)
    assert len(items) == 2
    assert items[0].id > items[1].id
