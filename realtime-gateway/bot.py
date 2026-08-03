"""Sherlock realtime gateway entry point."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from loguru import logger
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import TransportParams

load_dotenv(override=True)


def _configure_runtime_logging() -> None:
    log_level = os.getenv("REALTIME_GATEWAY_LOG_LEVEL", "INFO").upper()
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        filter=lambda record: not (
            record["name"] == "pipecat.runner.run"
            and record["message"].startswith("Received request:")
        ),
    )


async def bot(runner_args: RunnerArguments):
    """Main entry point for the bot runner (called by pipecat.runner.run.main)."""

    mode = os.getenv("AI_MODE", "cascade").strip().lower()
    agent_runtime = os.getenv("AGENT_RUNTIME", "standalone").strip().lower()
    logger.info(f"AI_MODE = {mode}; AGENT_RUNTIME = {agent_runtime}")

    if mode != "cascade":
        raise RuntimeError(
            f"Unsupported AI_MODE '{mode}'. This project only supports AI_MODE=cascade."
        )

    # ── shared transport params ────────────────────────────────────────
    transport_params = {
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            video_in_enabled=True,
        )
    }
    transport = await create_transport(runner_args, transport_params)

    if agent_runtime == "yuxi":
        from bot_yuxi import run_bot_yuxi

        await run_bot_yuxi(transport, runner_args)
    elif agent_runtime == "standalone":
        from bot_cascade import run_bot_cascade

        await run_bot_cascade(transport, runner_args)
    else:
        raise RuntimeError(
            f"Unsupported AGENT_RUNTIME '{agent_runtime}'. Supported: standalone, yuxi."
        )


if __name__ == "__main__":
    from pipecat.runner.run import app, main

    from frame_broker import router as realtime_internal_router

    if os.getenv("AGENT_RUNTIME", "standalone").strip().lower() == "yuxi":
        import bot_yuxi  # noqa: F401

    app.include_router(realtime_internal_router)
    app.router.add_event_handler("startup", _configure_runtime_logging)
    main()
