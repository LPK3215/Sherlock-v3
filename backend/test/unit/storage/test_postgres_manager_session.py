from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from yuxi.storage.postgres.manager import PostgresManager


class _Session:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True

    async def close(self):
        self.closed = True


@pytest.fixture
def manager(monkeypatch):
    manager = PostgresManager()
    session = _Session()
    monkeypatch.setattr(manager, "initialize", lambda: None)
    manager.AsyncSession = lambda: session
    return manager, session


@pytest.mark.asyncio
async def test_session_context_commits_and_closes_on_success(manager):
    manager, session = manager

    async with manager.get_async_session_context() as current_session:
        assert current_session is session

    assert session.committed is True
    assert session.rolled_back is False
    assert session.closed is True


@pytest.mark.asyncio
async def test_session_context_rolls_back_and_logs_database_errors(manager, monkeypatch):
    manager, session = manager
    errors = []
    monkeypatch.setattr(
        "yuxi.storage.postgres.manager.logger",
        SimpleNamespace(error=errors.append),
    )
    database_error = OperationalError("query failed", {}, RuntimeError("connection lost"))

    with pytest.raises(OperationalError, match="query failed"):
        async with manager.get_async_session_context():
            raise database_error

    assert session.committed is False
    assert session.rolled_back is True
    assert session.closed is True
    assert errors == [f"PostgreSQL async operation failed: {database_error}"]


@pytest.mark.asyncio
async def test_session_context_rolls_back_without_mislabeling_business_errors(manager, monkeypatch):
    manager, session = manager
    errors = []
    monkeypatch.setattr(
        "yuxi.storage.postgres.manager.logger",
        SimpleNamespace(error=errors.append),
    )
    business_error = ValueError("invalid request")

    with pytest.raises(ValueError, match="invalid request"):
        async with manager.get_async_session_context():
            raise business_error

    assert session.committed is False
    assert session.rolled_back is True
    assert session.closed is True
    assert errors == []
