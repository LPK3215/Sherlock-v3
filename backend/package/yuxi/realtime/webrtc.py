"""SmallWebRTC media-track handling required by camera and screen capture."""

from __future__ import annotations

from aiortc.sdp import SessionDescription
from pipecat.transports.smallwebrtc.connection import SCREEN_VIDEO_TRANSCEIVER_INDEX

from yuxi.utils.logging_config import logger


def bind_remote_media_sources(pc):
    remote_description = pc.remoteDescription
    if not remote_description:
        return []

    media_sections = SessionDescription.parse(remote_description.sdp).media
    transceivers = pc.getTransceivers()
    routers = []
    for transceiver in transceivers:
        router = transceiver.receiver.transport._rtp_router
        if all(router is not existing for existing in routers):
            routers.append(router)

    for index, media in enumerate(media_sections):
        if index >= len(transceivers):
            break
        receiver = transceivers[index].receiver
        for router in routers:
            for payload_type in media.fmt:
                if isinstance(payload_type, int):
                    router.payload_type_table.setdefault(payload_type, set()).add(receiver)
            for ssrc in media.ssrc:
                router.ssrc_table[ssrc.ssrc] = receiver
    return media_sections


def refresh_screen_video_track(client, connection, track) -> bool:
    transceivers = connection.pc.getTransceivers()
    if len(transceivers) <= SCREEN_VIDEO_TRANSCEIVER_INDEX:
        return False

    receiver = transceivers[SCREEN_VIDEO_TRANSCEIVER_INDEX].receiver
    if receiver.track is not track:
        return False

    connection._track_map.pop(SCREEN_VIDEO_TRANSCEIVER_INDEX, None)
    client._screen_video_track = connection.screen_video_input_track()
    return client._screen_video_track is not None


async def request_video_keyframe(connection, source: str) -> None:
    transceiver_index = SCREEN_VIDEO_TRANSCEIVER_INDEX if source == "screen" else 1
    transceivers = connection.pc.getTransceivers()
    if len(transceivers) <= transceiver_index:
        logger.warning(f"Cannot request {source} keyframe: transceiver is unavailable")
        return

    transceiver = transceivers[transceiver_index]
    receiver = transceiver.receiver
    if source == "screen":
        _bind_bundled_transport(connection.pc, transceiver)
        await _ensure_receiver_started(connection.pc, transceiver)

    media_sections = bind_remote_media_sources(connection.pc)
    if len(media_sections) > transceiver_index and media_sections[transceiver_index].ssrc:
        await receiver._send_rtcp_pli(media_sections[transceiver_index].ssrc[0].ssrc)
        return

    logger.warning(f"Cannot request {source} keyframe: negotiated SSRC is unavailable")


async def _ensure_receiver_started(pc, transceiver) -> None:
    receiver = transceiver.receiver
    if getattr(receiver, "_RTCRtpReceiver__started", False):
        return
    await receiver.receive(pc._RTCPeerConnection__remoteRtp(transceiver))


def _bind_bundled_transport(pc, transceiver) -> None:
    primary_transport = pc.getTransceivers()[0].receiver.transport
    if transceiver.receiver.transport is primary_transport:
        return

    transceiver.receiver.setTransport(primary_transport)
    transceiver.sender.setTransport(primary_transport)
    transceiver._bundled = True
