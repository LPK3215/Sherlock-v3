from __future__ import annotations

from types import SimpleNamespace

import pytest

from yuxi.agents.toolkits import service as tool_service


def test_get_tool_metadata_includes_config_guide(monkeypatch):
    tool_service._metadata_cache.clear()

    fake_tool = SimpleNamespace(
        name="demo_tool",
        description="demo description",
        metadata={},
        args_schema=None,
    )
    fake_extra = SimpleNamespace(
        category="buildin",
        tags=["demo"],
        display_name="演示工具",
        config_guide="请先配置 DEMO_API_KEY",
    )

    monkeypatch.setattr(
        "yuxi.agents.toolkits.registry.get_all_tool_instances",
        lambda: [fake_tool],
    )
    monkeypatch.setattr(
        "yuxi.agents.toolkits.registry.get_all_extra_metadata",
        lambda: {"demo_tool": fake_extra},
    )

    result = tool_service.get_tool_metadata()

    assert result == [
        {
            "slug": "demo_tool",
            "name": "演示工具",
            "description": "demo description",
            "metadata": {},
            "args": [],
            "category": "buildin",
            "tags": ["demo"],
            "config_guide": "请先配置 DEMO_API_KEY",
        }
    ]

    tool_service._metadata_cache.clear()


def test_extract_tool_info_ignores_unserializable_injected_schema():
    class BrokenSchema:
        def model_json_schema(self):
            raise ValueError("injected callable cannot be serialized")

    fake_tool = SimpleNamespace(
        name="runtime_tool",
        description="runtime tool",
        metadata={},
        args_schema=BrokenSchema(),
    )

    assert tool_service._extract_tool_info(fake_tool)["args"] == []


@pytest.mark.asyncio
async def test_realtime_tools_are_only_available_in_realtime_context(monkeypatch):
    realtime_tool = SimpleNamespace(name="capture_live_camera")

    monkeypatch.setattr(
        tool_service,
        "get_tool_instances_by_category",
        lambda category: [realtime_tool] if category == "realtime" else [],
    )
    monkeypatch.setattr(
        "yuxi.agents.middlewares.skills.resolve_skill_gated_tools",
        lambda _context: [],
    )

    web_tools = await tool_service.resolve_configured_runtime_tools(
        SimpleNamespace(tools=[], mcps=[], realtime_session_id=None)
    )
    realtime_tools = await tool_service.resolve_configured_runtime_tools(
        SimpleNamespace(tools=[], mcps=[], realtime_session_id="rt-session-1")
    )

    assert web_tools == []
    assert realtime_tools == [realtime_tool]
