"""Cascade voice/video bot entry point."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from loguru import logger
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import TransportParams

load_dotenv(override=True)


async def bot(runner_args: RunnerArguments):
    """Main entry point for the bot runner (called by pipecat.runner.run.main)."""

    mode = os.getenv("AI_MODE", "cascade").strip().lower()
    logger.info(f"AI_MODE = {mode}")

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

    from bot_cascade import run_bot_cascade

    await run_bot_cascade(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
