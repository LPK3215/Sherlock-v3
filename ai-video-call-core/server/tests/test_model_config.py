import unittest

from model_config import ModelConfigurationError, load_model_config


class ModelConfigTests(unittest.TestCase):
    def test_loads_native_realtime_without_exposing_key(self):
        config = load_model_config(
            "realtime",
            "google",
            {"GOOGLE_API_KEY": "secret", "GEMINI_LIVE_MODEL": "gemini-live-test"},
        )

        realtime = config.realtime
        assert realtime is not None
        self.assertEqual(realtime.provider, "google")
        self.assertEqual(realtime.model, "gemini-live-test")
        self.assertNotIn("secret", repr(config))
        self.assertNotIn("api_key", str(config.public_summary()))

    def test_loads_independent_mixed_cascade_services(self):
        config = load_model_config(
            "cascade",
            "openai-compatible",
            {
                "CASCADE_STT_PROVIDER": "google",
                "GOOGLE_CREDENTIALS_JSON": "{}",
                "CASCADE_VLM_API_KEY": "modelscope-key",
                "CASCADE_VLM_BASE_URL": "https://api-inference.modelscope.cn/v1/",
                "CASCADE_VLM_MODEL": "Qwen/example-vl",
                "CASCADE_TTS_PROVIDER": "openai-compatible",
                "CASCADE_TTS_API_KEY": "local-key",
                "CASCADE_TTS_BASE_URL": "http://127.0.0.1:9000/v1/",
                "CASCADE_TTS_MODEL": "local-tts",
                "CASCADE_TTS_VOICE": "zh-voice",
            },
        )

        stt, vlm, tts = config.stt, config.vlm, config.tts
        assert stt is not None and vlm is not None and tts is not None
        self.assertEqual(stt.provider, "google")
        self.assertEqual(vlm.provider, "openai-compatible")
        self.assertEqual(vlm.base_url, "https://api-inference.modelscope.cn/v1")
        self.assertEqual(vlm.model, "Qwen/example-vl")
        self.assertEqual(vlm.adapter, "qwen")
        self.assertEqual(tts.provider, "openai-compatible")
        self.assertEqual(tts.base_url, "http://127.0.0.1:9000/v1")

    def test_native_cascade_keeps_backward_compatible_provider_defaults(self):
        config = load_model_config("cascade", "openai", {"OPENAI_API_KEY": "secret"})

        stt, vlm, tts = config.stt, config.vlm, config.tts
        assert stt is not None and vlm is not None and tts is not None
        self.assertEqual(stt.provider, "openai")
        self.assertEqual(vlm.provider, "openai")
        self.assertEqual(tts.provider, "openai")

    def test_compatible_vlm_values_do_not_leak_into_native_profile(self):
        config = load_model_config(
            "cascade",
            "openai",
            {
                "OPENAI_API_KEY": "openai-key",
                "CASCADE_VLM_API_KEY": "modelscope-key",
                "CASCADE_VLM_BASE_URL": "https://api-inference.modelscope.cn/v1",
                "CASCADE_VLM_MODEL": "Qwen/example-vl",
                "OPENAI_LLM_MODEL": "gpt-native",
            },
        )

        vlm = config.vlm
        assert vlm is not None
        self.assertEqual(vlm.api_key, "openai-key")
        self.assertEqual(vlm.model, "gpt-native")
        self.assertIsNone(vlm.base_url)

    def test_compatible_vlm_requires_key_endpoint_and_model(self):
        with self.assertRaisesRegex(ModelConfigurationError, "CASCADE_VLM_API_KEY"):
            load_model_config(
                "cascade",
                "openai-compatible",
                {
                    "OPENAI_API_KEY": "voice-key",
                    "CASCADE_VLM_BASE_URL": "https://example.test/v1",
                    "CASCADE_VLM_MODEL": "qwen-vl",
                },
            )

    def test_compatible_endpoint_is_not_accepted_as_realtime(self):
        with self.assertRaisesRegex(ModelConfigurationError, "belong in cascade"):
            load_model_config("realtime", "openai-compatible", {})

    def test_compatible_non_qwen_model_uses_generic_openai_adapter(self):
        config = load_model_config(
            "cascade",
            "openai-compatible",
            {
                "OPENAI_API_KEY": "voice-key",
                "CASCADE_VLM_API_KEY": "vlm-key",
                "CASCADE_VLM_BASE_URL": "https://example.test/v1",
                "CASCADE_VLM_MODEL": "other/vision-model",
            },
        )

        vlm = config.vlm
        assert vlm is not None
        self.assertEqual(vlm.adapter, "openai")


if __name__ == "__main__":
    unittest.main()
