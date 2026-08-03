from __future__ import annotations

import base64

import pytest
from pipecat.frames.frames import UserImageRawFrame, UserImageRequestFrame
from pipecat.processors.frame_processor import FrameDirection

from frame_broker import FrameBroker


@pytest.mark.asyncio
async def test_frame_broker_returns_fresh_requested_frame(monkeypatch: pytest.MonkeyPatch):
    keyframe_sources = []

    async def request_keyframe(source):
        keyframe_sources.append(source)

    broker = FrameBroker(
        session_id="rt-1",
        uid="user-1",
        request_video_keyframe=request_keyframe,
    )
    broker.user_id = "transport-user"

    async def push_frame(frame, direction=FrameDirection.DOWNSTREAM):
        assert isinstance(frame, UserImageRequestFrame)
        assert direction is FrameDirection.UPSTREAM
        raw = UserImageRawFrame(
            image=bytes([255, 0, 0] * 4),
            size=(2, 2),
            format="RGB",
            user_id="transport-user",
            request=frame,
        )
        await broker.process_frame(raw, FrameDirection.DOWNSTREAM)

    monkeypatch.setattr(broker, "push_frame", push_frame)

    result = await broker.capture("camera", 1000)

    assert result["session_id"] == "rt-1"
    assert result["source"] == "camera"
    assert result["width"] == 2
    assert result["height"] == 2
    assert base64.b64decode(result["data_base64"]).startswith(b"\xff\xd8")
    assert keyframe_sources == ["camera"]


@pytest.mark.asyncio
async def test_screen_capture_requests_keyframe(monkeypatch: pytest.MonkeyPatch):
    events = []

    async def request_keyframe(source):
        events.append(("keyframe", source))

    broker = FrameBroker(
        session_id="rt-1",
        uid="user-1",
        request_video_keyframe=request_keyframe,
    )
    broker.user_id = "transport-user"

    async def sleep(delay):
        events.append(("sleep", delay))

    async def push_frame(frame, direction=FrameDirection.DOWNSTREAM):
        events.append(("request", frame.video_source))
        raw = UserImageRawFrame(
            image=bytes([0, 255, 0] * 4),
            size=(2, 2),
            format="RGB",
            user_id="transport-user",
            request=frame,
        )
        await broker.process_frame(raw, FrameDirection.DOWNSTREAM)

    monkeypatch.setattr("frame_broker.asyncio.sleep", sleep)
    monkeypatch.setattr(broker, "push_frame", push_frame)

    result = await broker.capture("screen", 1000)

    assert events == [
        ("request", "screenVideo"),
        ("sleep", 0),
        ("keyframe", "screen"),
    ]
    assert result["source"] == "screen"
