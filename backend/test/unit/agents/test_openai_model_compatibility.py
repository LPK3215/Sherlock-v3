from langchain_core.messages import AIMessageChunk

from yuxi.agents.models import _ToolCallChunkFixChatOpenAI


def _model(model_name: str) -> _ToolCallChunkFixChatOpenAI:
    return _ToolCallChunkFixChatOpenAI(model=model_name, api_key="test-key")


def test_qwen3_vl_instruct_promotes_nonstream_reasoning_answer_to_content() -> None:
    result = _model("Qwen/Qwen3-VL-8B-Instruct")._create_chat_result(
        {
            "model": "Qwen/Qwen3-VL-8B-Instruct",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "CAMERA RED 742",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
    )

    message = result.generations[0].message
    assert message.content == "CAMERA RED 742"
    assert message.additional_kwargs["reasoning_content"] == "CAMERA RED 742"


def test_qwen3_vl_instruct_promotes_stream_reasoning_answer_to_content() -> None:
    generation = _model("Qwen/Qwen3-VL-8B-Instruct")._convert_chunk_to_generation_chunk(
        {
            "model": "Qwen/Qwen3-VL-8B-Instruct",
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "CAMERA RED 742",
                    },
                    "finish_reason": None,
                }
            ],
        },
        AIMessageChunk,
        None,
    )

    assert generation is not None
    assert generation.message.content == "CAMERA RED 742"
    assert generation.message.additional_kwargs["reasoning_content"] == "CAMERA RED 742"


def test_reasoning_model_preserves_reasoning_without_promoting_it() -> None:
    result = _model("deepseek-ai/DeepSeek-R1")._create_chat_result(
        {
            "model": "deepseek-ai/DeepSeek-R1",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "internal reasoning",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
    )

    message = result.generations[0].message
    assert message.content == ""
    assert message.additional_kwargs["reasoning_content"] == "internal reasoning"


def test_qwen3_vl_instruct_does_not_replace_existing_content_or_tool_calls() -> None:
    result = _model("Qwen/Qwen3-VL-8B-Instruct")._create_chat_result(
        {
            "model": "Qwen/Qwen3-VL-8B-Instruct",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "visible answer",
                        "reasoning_content": "hidden detail",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {"name": "capture_live_camera", "arguments": "{}"},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
    )

    message = result.generations[0].message
    assert message.content == "visible answer"
    assert message.tool_calls[0]["name"] == "capture_live_camera"
    assert message.additional_kwargs["reasoning_content"] == "hidden detail"
