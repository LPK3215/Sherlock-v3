from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot_yuxi import (
    _bind_bundled_transport,
    _bind_remote_media_sources,
    _ensure_receiver_started,
    _refresh_screen_video_track,
)


class Receiver:
    def __init__(self, router):
        self.transport = SimpleNamespace(_rtp_router=router)


def test_bind_remote_media_sources_routes_each_ssrc_to_its_transceiver():
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

    media_sections = _bind_remote_media_sources(pc)

    assert len(media_sections) == 3
    for router in routers:
        assert router.ssrc_table == {11: receivers[0], 22: receivers[1], 33: receivers[2]}
        assert router.payload_type_table[111] == {receivers[0]}
        assert router.payload_type_table[96] == {receivers[1], receivers[2]}
        assert router.payload_type_table[97] == {receivers[1], receivers[2]}


def test_refresh_screen_video_track_replaces_inactive_cached_wrapper():
    remote_track = object()
    stale_wrapper = SimpleNamespace(_track=None)
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
        assert 2 not in connection._track_map
        connection._track_map[2] = refreshed_wrapper
        return refreshed_wrapper

    connection.screen_video_input_track = screen_video_input_track

    assert _refresh_screen_video_track(client, connection, remote_track)
    assert connection._track_map[2] is refreshed_wrapper
    assert client._screen_video_track is refreshed_wrapper


@pytest.mark.asyncio
async def test_ensure_receiver_started_loads_renegotiated_codec_parameters():
    received = []
    parameters = object()

    class Receiver:
        _RTCRtpReceiver__started = False

        async def receive(self, value):
            received.append(value)

    receiver = Receiver()
    transceiver = SimpleNamespace(receiver=receiver)
    pc = SimpleNamespace(
        _RTCPeerConnection__remoteRtp=lambda current: (
            parameters if current is transceiver else None
        )
    )

    await _ensure_receiver_started(pc, transceiver)

    assert received == [parameters]


def test_bind_bundled_transport_moves_screen_receiver_to_primary_transport():
    primary_transport = object()
    old_transport = object()
    receiver_transports = []
    sender_transports = []
    primary = SimpleNamespace(receiver=SimpleNamespace(transport=primary_transport))
    screen = SimpleNamespace(
        receiver=SimpleNamespace(
            transport=old_transport,
            setTransport=receiver_transports.append,
        ),
        sender=SimpleNamespace(setTransport=sender_transports.append),
        _bundled=False,
    )
    pc = SimpleNamespace(getTransceivers=lambda: [primary, SimpleNamespace(), screen])

    _bind_bundled_transport(pc, screen)

    assert receiver_transports == [primary_transport]
    assert sender_transports == [primary_transport]
    assert screen._bundled is True
