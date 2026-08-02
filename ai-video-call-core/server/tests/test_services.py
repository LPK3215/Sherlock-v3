import os
import unittest
from types import SimpleNamespace
from typing import cast

os.environ.setdefault("NLTK_DISABLE_IMPORT_SECURITY", "1")

from pipecat.frames.frames import UserImageRequestFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.llm_service import FunctionCallParams

from bot import (
    SessionResources,
    build_stt_service,
    build_tts_service,
    build_vlm_service,
    fetch_camera_image,
)
from model_config import ServiceModelConfig


class FakeLLM:
    def __init__(self):
        self.pushed = []

    async def push_frame(self, frame, direction):
        self.pushed.append((frame, direction))


class ServiceFactoryTests(unittest.TestCase):
    def test_compatible_vlm_uses_configured_endpoint_and_model(self):
        service = build_vlm_service(
            ServiceModelConfig(
                component="vlm",
                provider="openai-compatible",
                api_key="test-key",
                base_url="https://example.test/v1",
                model="qwen-vl-test",
            )
        )

        self.assertEqual(service._settings.model, "qwen-vl-test")
        self.assertEqual(str(service._client.base_url), "https://example.test/v1/")

    def test_qwen_vlm_uses_pipecat_qwen_adapter(self):
        service = build_vlm_service(
            ServiceModelConfig(
                component="vlm",
                provider="openai-compatible",
                adapter="qwen",
                api_key="test-key",
                base_url="https://api-inference.modelscope.cn/v1",
                model="Qwen/Qwen3-VL-8B-Instruct",
            )
        )

        self.assertEqual(type(service).__name__, "QwenLLMService")
        self.assertEqual(service._settings.model, "Qwen/Qwen3-VL-8B-Instruct")
        self.assertFalse(service.supports_developer_role)

    def test_compatible_stt_and_tts_use_their_own_endpoints(self):
        stt = build_stt_service(
            ServiceModelConfig(
                component="stt",
                provider="openai-compatible",
                api_key="stt-key",
                base_url="http://127.0.0.1:8100/v1",
                model="whisper-test",
            )
        )
        tts = build_tts_service(
            ServiceModelConfig(
                component="tts",
                provider="openai-compatible",
                api_key="tts-key",
                base_url="http://127.0.0.1:8200/v1",
                model="tts-test",
                voice="voice-test",
            )
        )

        self.assertEqual(str(stt._client.base_url), "http://127.0.0.1:8100/v1/")
        self.assertEqual(stt._settings.model, "whisper-test")
        self.assertEqual(str(tts._client.base_url), "http://127.0.0.1:8200/v1/")
        self.assertEqual(tts._settings.model, "tts-test")
        self.assertEqual(tts._settings.voice, "voice-test")


class VisualToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_camera_tool_uses_connected_participant_and_requests_image(self):
        llm = FakeLLM()
        results = []

        async def result_callback(result, **kwargs):
            results.append((result, kwargs))

        params = cast(
            FunctionCallParams,
            SimpleNamespace(
                app_resources=SessionResources(user_id="participant-42"),
                function_name="fetch_camera_image",
                tool_call_id="tool-1",
                result_callback=result_callback,
                llm=llm,
            ),
        )

        await fetch_camera_image(params, "What am I holding?")

        self.assertEqual(results, [])
        self.assertEqual(len(llm.pushed), 1)
        frame, direction = llm.pushed[0]
        self.assertIsInstance(frame, UserImageRequestFrame)
        self.assertEqual(frame.user_id, "participant-42")
        self.assertEqual(frame.video_source, "camera")
        self.assertEqual(frame.text, "What am I holding?")
        self.assertTrue(frame.append_to_context)
        self.assertEqual(direction, FrameDirection.UPSTREAM)

    async def test_camera_tool_returns_clear_error_before_connection(self):
        llm = FakeLLM()
        results = []

        async def result_callback(result, **kwargs):
            results.append((result, kwargs))

        params = cast(
            FunctionCallParams,
            SimpleNamespace(
                app_resources=SessionResources(),
                function_name="fetch_camera_image",
                tool_call_id="tool-1",
                result_callback=result_callback,
                llm=llm,
            ),
        )

        await fetch_camera_image(params, "Can you see me?")

        self.assertEqual(len(results), 1)
        self.assertIn("not connected", results[0][0]["error"])
        self.assertEqual(llm.pushed, [])


if __name__ == "__main__":
    unittest.main()
