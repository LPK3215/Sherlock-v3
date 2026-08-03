import pytest
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command

from yuxi.agents.toolkits import realtime as realtime_toolkit
from yuxi.agents.toolkits.realtime import capture_live_camera, capture_live_screen


def test_realtime_tool_input_schemas_exclude_injected_runtime_arguments():
    for realtime_tool in (capture_live_camera, capture_live_screen):
        schema = realtime_tool.args_schema.model_json_schema()

        assert schema["properties"] == {}
        assert realtime_tool.args == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("realtime_tool", "expected_source"),
    ((capture_live_camera, "camera"), (capture_live_screen, "screen")),
)
async def test_realtime_tool_runtime_reaches_coroutine(
    monkeypatch: pytest.MonkeyPatch,
    realtime_tool,
    expected_source: str,
):
    runtime = ToolRuntime(
        state={},
        context=None,
        config={},
        stream_writer=lambda _value: None,
        tool_call_id="call-1",
        store=None,
        tools=[],
    )
    captured = {}

    async def capture(source: str, injected_runtime: ToolRuntime, tool_call_id: str) -> Command:
        captured.update(source=source, runtime=injected_runtime, tool_call_id=tool_call_id)
        return Command(
            update={
                "messages": [
                    ToolMessage(content="captured", tool_call_id=tool_call_id),
                ]
            }
        )

    monkeypatch.setattr(realtime_toolkit.tools, "_capture_live_frame", capture)

    result = await realtime_tool.ainvoke(
        {
            "name": realtime_tool.name,
            "args": {"runtime": runtime},
            "id": "call-1",
            "type": "tool_call",
        }
    )

    assert isinstance(result, Command)
    assert captured == {
        "source": expected_source,
        "runtime": runtime,
        "tool_call_id": "call-1",
    }
