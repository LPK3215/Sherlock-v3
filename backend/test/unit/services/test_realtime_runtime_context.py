from __future__ import annotations

import pytest

from yuxi.services.agent_run_service import _prepare_run_input_message
from yuxi.services.chat_service import _apply_realtime_runtime_context
from yuxi.services.input_message_service import build_chat_input_message


def test_realtime_session_metadata_reaches_runtime_context():
    input_message = _prepare_run_input_message(
        run_type="chat",
        input_message=build_chat_input_message("查看摄像头"),
        resume=None,
        request_id="request-1",
        model_spec="provider/model",
        meta={"source": "realtime", "realtime_session_id": "rt-session-1"},
    )
    context = {}

    _apply_realtime_runtime_context(context, input_message.extra_metadata)

    assert input_message.extra_metadata["realtime_session_id"] == "rt-session-1"
    assert context["realtime_session_id"] == "rt-session-1"


def test_realtime_runtime_requires_server_session_id():
    with pytest.raises(ValueError, match="realtime_session_id"):
        _apply_realtime_runtime_context({}, {"source": "realtime"})


def test_non_realtime_runtime_is_unchanged():
    context = {"system_prompt": "unchanged"}

    _apply_realtime_runtime_context(context, {"source": "web"})

    assert context == {"system_prompt": "unchanged"}


def test_realtime_runtime_preserves_resolved_agent_capabilities():
    context = {
        "system_prompt": "Use configured capabilities",
        "tools": ["present_artifacts"],
        "skills": ["knowledge-base"],
        "mcps": ["mcp-server-chart"],
        "knowledges": ["kb-1"],
        "subagents": ["general-purpose"],
        "_runtime_skill_dependency_map": {
            "knowledge-base": {"tools": ["query_kb"]},
        },
    }

    _apply_realtime_runtime_context(
        context,
        {"source": "realtime", "realtime_session_id": "rt-session-1"},
    )

    assert context == {
        "system_prompt": "Use configured capabilities",
        "tools": ["present_artifacts"],
        "skills": ["knowledge-base"],
        "mcps": ["mcp-server-chart"],
        "knowledges": ["kb-1"],
        "subagents": ["general-purpose"],
        "_runtime_skill_dependency_map": {
            "knowledge-base": {"tools": ["query_kb"]},
        },
        "realtime_session_id": "rt-session-1",
    }


def test_realtime_request_metadata_cannot_override_resolved_agent_capabilities():
    context = {
        "system_prompt": "Authorized prompt",
        "tools": ["allowed_tool"],
        "skills": ["allowed-skill"],
        "mcps": ["allowed-mcp"],
        "knowledges": ["allowed-kb"],
        "subagents": ["allowed-subagent"],
    }

    _apply_realtime_runtime_context(
        context,
        {
            "source": "realtime",
            "realtime_session_id": "rt-session-1",
            "system_prompt": "Injected prompt",
            "tools": ["forbidden_tool"],
            "skills": ["forbidden-skill"],
            "mcps": ["forbidden-mcp"],
            "knowledges": ["forbidden-kb"],
            "subagents": ["forbidden-subagent"],
        },
    )

    assert context == {
        "system_prompt": "Authorized prompt",
        "tools": ["allowed_tool"],
        "skills": ["allowed-skill"],
        "mcps": ["allowed-mcp"],
        "knowledges": ["allowed-kb"],
        "subagents": ["allowed-subagent"],
        "realtime_session_id": "rt-session-1",
    }
