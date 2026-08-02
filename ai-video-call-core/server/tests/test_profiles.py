import unittest

from profiles import (
    ProfileConfigurationError,
    SessionProfile,
    assemble_pipeline_processors,
    parse_session_profile,
    validate_profile_environment,
)


class SessionProfileTests(unittest.TestCase):
    def test_defaults_to_google_realtime(self):
        self.assertEqual(parse_session_profile({}).name, "realtime/google")

    def test_parses_runner_body_and_nested_request_data(self):
        self.assertEqual(
            parse_session_profile({"mode": "cascade", "provider": "openai"}).name,
            "cascade/openai",
        )
        self.assertEqual(
            parse_session_profile(
                {"requestData": {"body": {"mode": "realtime", "provider": "openai"}}}
            ).name,
            "realtime/openai",
        )
        self.assertEqual(
            parse_session_profile({"mode": "cascade", "provider": "openai_compatible"}).name,
            "cascade/openai-compatible",
        )

    def test_rejects_unknown_values(self):
        with self.assertRaisesRegex(ProfileConfigurationError, "Unsupported AI mode"):
            parse_session_profile({"mode": "batch"})
        with self.assertRaisesRegex(ProfileConfigurationError, "Unsupported AI provider"):
            parse_session_profile({"provider": "unknown"})
        with self.assertRaisesRegex(ProfileConfigurationError, "Realtime mode supports"):
            parse_session_profile({"mode": "realtime", "provider": "openai-compatible"})

    def test_validates_each_profile_credentials(self):
        validate_profile_environment(SessionProfile("realtime", "google"), {"GOOGLE_API_KEY": "x"})
        validate_profile_environment(SessionProfile("cascade", "openai"), {"OPENAI_API_KEY": "x"})
        validate_profile_environment(
            SessionProfile("cascade", "google"),
            {"GOOGLE_API_KEY": "x", "GOOGLE_APPLICATION_CREDENTIALS": "service.json"},
        )
        with self.assertRaisesRegex(ProfileConfigurationError, "GOOGLE_CREDENTIALS_JSON"):
            validate_profile_environment(
                SessionProfile("cascade", "google"), {"GOOGLE_API_KEY": "x"}
            )

    def test_assembles_realtime_pipeline(self):
        profile = SessionProfile("realtime", "openai")
        processors = assemble_pipeline_processors(
            profile,
            transport_input="input",
            user_aggregator="user",
            llm="llm",
            transport_output="output",
            assistant_aggregator="assistant",
        )
        self.assertEqual(processors, ["input", "user", "llm", "output", "assistant"])
        self.assertEqual(profile.pipeline_steps[2], "realtime_llm")

    def test_assembles_cascade_pipeline(self):
        profile = SessionProfile("cascade", "google")
        processors = assemble_pipeline_processors(
            profile,
            transport_input="input",
            stt="stt",
            user_aggregator="user",
            llm="llm",
            tts="tts",
            transport_output="output",
            assistant_aggregator="assistant",
        )
        self.assertEqual(
            processors,
            ["input", "stt", "user", "llm", "tts", "output", "assistant"],
        )

    def test_cascade_rejects_missing_voice_service(self):
        with self.assertRaisesRegex(ProfileConfigurationError, "requires both STT and TTS"):
            assemble_pipeline_processors(
                SessionProfile("cascade", "openai"),
                transport_input="input",
                user_aggregator="user",
                llm="llm",
                transport_output="output",
                assistant_aggregator="assistant",
            )


if __name__ == "__main__":
    unittest.main()
