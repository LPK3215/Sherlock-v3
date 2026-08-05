from __future__ import annotations

import pytest

from yuxi.realtime.manager import RealtimeSessionManager


def test_realtime_session_owner_is_required():
    manager = RealtimeSessionManager()
    session = manager.create_session(uid="owner", agent_slug="agent", thread_id="thread")

    assert manager._get_owned_session(session.session_id, "owner") is session

    with pytest.raises(PermissionError):
        manager._get_owned_session(session.session_id, "other")

    with pytest.raises(LookupError):
        manager._get_owned_session("missing", "owner")
