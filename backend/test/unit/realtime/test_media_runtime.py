from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest
from pipecat.frames.frames import UserImageRawFrame, UserImageRequestFrame
from pipecat.processors.frame_processor import FrameDirection

from yuxi.realtime.manager import RealtimeSessionManager
from yuxi.realtime.pipeline import FrameBroker, RealtimeSessionConfig
from yuxi.realtime.webrtc import (
    _bind_bundled_transport,
    _ensure_receiver_started,
    bind_remote_media_sources,
    refresh_screen_video_track,
)


@pytest.mark.asyncio
async def test_frame_broker_returns_requested_camera_frame(monkeypatch: pytest.MonkeyPatch):
    requested_keyframes = []

    async def request_keyframe(source: str) -> None:
        requested_keyframes.append(source)

    broker = FrameBroker(
        RealtimeSessionConfig("session-1", "user-1", "agent-1", "thread-1"),
        request_keyframe=request_keyframe,
    )
    broker.user_id = "transport-user"

    async def push_frame(frame, direction=FrameDirection.DOWNSTREAM):
        assert isinstance(frame, UserImageRequestFrame)
        assert direction is FrameDirection.UPSTREAM
        await broker.process_frame(
            UserImageRawFrame(
                image=bytes([255, 0, 0] * 4),
                size=(2, 2),
                format="RGB",
                user_id="transport-user",
                request=frame,
            ),
            FrameDirection.DOWNSTREAM,
        )

    monkeypatch.setattr(broker, "push_frame", push_frame)

    result = await broker.capture("camera", 1000)

    assert result["session_id"] == "session-1"
    assert result["source"] == "camera"
    assert result["width"] == 2
    assert result["height"] == 2
    assert base64.b64decode(result["data_base64"]).startswith(b"\xff\xd8")
    assert requested_keyframes == ["camera"]


@pytest.mark.asyncio
async def test_screen_capture_yields_before_requesting_keyframe(monkeypatch: pytest.MonkeyPatch):
    events = []

    async def request_keyframe(source: str) -> None:
        events.append(("keyframe", source))

    broker = FrameBroker(
        RealtimeSessionConfig("session-1", "user-1", "agent-1", "thread-1"),
        request_keyframe=request_keyframe,
    )
    broker.user_id = "transport-user"

    async def sleep(delay: float) -> None:
        events.append(("sleep", delay))

    async def push_frame(frame, direction=FrameDirection.DOWNSTREAM):
        events.append(("request", frame.video_source))
        await broker.process_frame(
            UserImageRawFrame(
                image=bytes([0, 255, 0] * 4),
                size=(2, 2),
                format="RGB",
                user_id="transport-user",
                request=frame,
            ),
            FrameDirection.DOWNSTREAM,
        )

    monkeypatch.setattr("yuxi.realtime.pipeline.asyncio.sleep", sleep)
    monkeypatch.setattr(broker, "push_frame", push_frame)

    result = await broker.capture("screen", 1000)

    assert events == [("request", "screenVideo"), ("sleep", 0), ("keyframe", "screen")]
    assert result["source"] == "screen"


def test_bind_remote_media_sources_routes_all_negotiated_tracks():
    class Receiver:
        def __init__(self, router):
            self.transport = SimpleNamespace(_rtp_router=router)

    routers = [SimpleNamespace(payload_type_table={}, ssrc_table={}) for _ in range(3)]
    receivers = [Receiver(router) for router in routers]
    pc = SimpleNamespace(
        remoteDescription=SimpleNamespace(
            sdp="\r\n".join(
                [
                    "v=0",
                    "o=- 1 1 IN IP4 127.0.0.1",
                    "s=-",
                    "t=0 0",
                    "m=audio 9 UDP/TLS/RTP/SAVPF 111",
                    "a=mid:0",
                    "a=ssrc:11 cname:audio",
                    "m=video 9 UDP/TLS/RTP/SAVPF 96 97",
                    "a=mid:1",
                    "a=ssrc:22 cname:camera",
                    "m=video 9 UDP/TLS/RTP/SAVPF 96 97",
                    "a=mid:2",
                    "a=ssrc:33 cname:screen",
                    "",
                ]
            )
        ),
        getTransceivers=lambda: [SimpleNamespace(receiver=receiver) for receiver in receivers],
    )

    bind_remote_media_sources(pc)

    for router in routers:
        assert router.ssrc_table == {11: receivers[0], 22: receivers[1], 33: receivers[2]}
        assert router.payload_type_table[111] == {receivers[0]}
        assert router.payload_type_table[96] == {receivers[1], receivers[2]}
        assert router.payload_type_table[97] == {receivers[1], receivers[2]}


def test_refresh_screen_video_track_replaces_cached_wrapper():
    remote_track = object()
    stale_wrapper = object()
    refreshed_wrapper = object()
    client = SimpleNamespace(_screen_video_track=stale_wrapper)
    connection = SimpleNamespace(
        pc=SimpleNamespace(
            getTransceivers=lambda: [
                SimpleNamespace(receiver=SimpleNamespace(track=object())),
                SimpleNamespace(receiver=SimpleNamespace(track=object())),
                SimpleNamespace(receiver=SimpleNamespace(track=remote_track)),
            ]
        ),
        _track_map={2: stale_wrapper},
    )

    def screen_video_input_track():
        connection._track_map[2] = refreshed_wrapper
        return refreshed_wrapper

    connection.screen_video_input_track = screen_video_input_track

    assert refresh_screen_video_track(client, connection, remote_track)
    assert connection._track_map[2] is refreshed_wrapper
    assert client._screen_video_track is refreshed_wrapper


@pytest.mark.asyncio
async def test_ensure_receiver_started_uses_renegotiated_parameters():
    received = []
    parameters = object()

    class Receiver:
        _RTCRtpReceiver__started = False

        async def receive(self, value):
            received.append(value)

    receiver = Receiver()
    transceiver = SimpleNamespace(receiver=receiver)
    pc = SimpleNamespace(_RTCPeerConnection__remoteRtp=lambda current: parameters)

    await _ensure_receiver_started(pc, transceiver)

    assert received == [parameters]


def test_bind_bundled_transport_moves_screen_to_primary_transport():
    primary_transport = object()
    receiver_transports = []
    sender_transports = []
    primary = SimpleNamespace(receiver=SimpleNamespace(transport=primary_transport))
    screen = SimpleNamespace(
        receiver=SimpleNamespace(transport=object(), setTransport=receiver_transports.append),
        sender=SimpleNamespace(setTransport=sender_transports.append),
        _bundled=False,
    )
    pc = SimpleNamespace(getTransceivers=lambda: [primary, SimpleNamespace(), screen])

    _bind_bundled_transport(pc, screen)

    assert receiver_transports == [primary_transport]
    assert sender_transports == [primary_transport]
    assert screen._bundled is True


def test_finished_pipeline_removes_session_and_task():
    manager = RealtimeSessionManager()
    session = manager.create_session(uid="user-1", agent_slug="agent-1", thread_id="thread-1")
    task = SimpleNamespace(cancelled=lambda: True)
    manager._tasks[session.session_id] = task

    manager._pipeline_finished(session.session_id, task)

    assert session.session_id not in manager._sessions
    assert session.session_id not in manager._tasks
