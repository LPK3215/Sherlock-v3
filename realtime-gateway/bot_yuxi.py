"""Realtime media pipeline using Yuxi as the only Agent runtime."""

from __future__ import annotations

import uuid

from aiortc.sdp import SessionDescription
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.utils import get_transport_client_id
from pipecat.transports.smallwebrtc.connection import SCREEN_VIDEO_TRANSCEIVER_INDEX
from pipecat.workers.runner import WorkerRunner

from bot_cascade import _make_stt_service, _make_tts_service
from frame_broker import FrameBroker, register_frame_broker, unregister_frame_broker
from yuxi_client import YuxiAgentClient, YuxiSessionConfig
from yuxi_llm import YuxiLLMService, YuxiResumeFrame, yuxi_agent_event_frame


def _bind_remote_media_sources(pc):
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


def _refresh_screen_video_track(client, connection, track) -> bool:
    transceivers = connection.pc.getTransceivers()
    if len(transceivers) <= SCREEN_VIDEO_TRANSCEIVER_INDEX:
        return False

    receiver = transceivers[SCREEN_VIDEO_TRANSCEIVER_INDEX].receiver
    if receiver.track is not track:
        return False

    connection._track_map.pop(SCREEN_VIDEO_TRANSCEIVER_INDEX, None)
    client._screen_video_track = connection.screen_video_input_track()
    return client._screen_video_track is not None


async def _ensure_receiver_started(pc, transceiver) -> None:
    receiver = transceiver.receiver
    if getattr(receiver, "_RTCRtpReceiver__started", False):
        return

    receive_parameters = pc._RTCPeerConnection__remoteRtp(transceiver)
    await receiver.receive(receive_parameters)


def _bind_bundled_transport(pc, transceiver) -> None:
    primary_transport = pc.getTransceivers()[0].receiver.transport
    if transceiver.receiver.transport is primary_transport:
        return

    transceiver.receiver.setTransport(primary_transport)
    transceiver.sender.setTransport(primary_transport)
    transceiver._bundled = True


async def run_bot_yuxi(transport, runner_args) -> None:
    session_id = runner_args.session_id or f"rt-{uuid.uuid4()}"
    config = YuxiSessionConfig.from_runner_body(runner_args.body, session_id=session_id)
    yuxi_client = YuxiAgentClient(config)
    uid = await yuxi_client.current_user_uid()
    transport_client = transport._client
    webrtc_connection = transport_client._webrtc_connection

    @webrtc_connection.event_handler("track-started")
    async def on_track_started(connection, track):
        if _refresh_screen_video_track(transport_client, connection, track):
            logger.debug("Refreshed screen input track after WebRTC renegotiation")

    async def request_video_keyframe(source: str) -> None:
        transceiver_index = 2 if source == "screen" else 1
        transceivers = webrtc_connection.pc.getTransceivers()
        if len(transceivers) <= transceiver_index:
            logger.warning("Cannot request {} keyframe: transceiver is unavailable", source)
            return

        receiver = transceivers[transceiver_index].receiver
        if source == "screen":
            _bind_bundled_transport(webrtc_connection.pc, transceivers[transceiver_index])
            await _ensure_receiver_started(
                webrtc_connection.pc, transceivers[transceiver_index]
            )
        media_sections = _bind_remote_media_sources(webrtc_connection.pc)
        if len(media_sections) > transceiver_index:
            media = media_sections[transceiver_index]
            if media.ssrc:
                await receiver._send_rtcp_pli(media.ssrc[0].ssrc)
                return

        logger.warning("Cannot request {} keyframe: negotiated SSRC is unavailable", source)

    frame_broker = FrameBroker(
        session_id=session_id,
        uid=uid,
        request_video_keyframe=request_video_keyframe,
    )
    register_frame_broker(frame_broker)
    yuxi_llm = YuxiLLMService(yuxi_client)
    yuxi_llm._frame_broker = frame_broker
    stt = _make_stt_service()
    tts = _make_tts_service()

    context = LLMContext(messages=[])
    vad = SileroVADAnalyzer(params=VADParams(stop_secs=0.8, start_secs=0.08, confidence=0.4))
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        realtime_service_mode=False,
        user_params=LLMUserAggregatorParams(vad_analyzer=vad),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            frame_broker,
            stt,
            user_aggregator,
            yuxi_llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=None,
    )
    pending_interrupt_restore_started = False

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        nonlocal pending_interrupt_restore_started
        _bind_remote_media_sources(webrtc_connection.pc)
        frame_broker.user_id = get_transport_client_id(transport, client)
        logger.info(
            "Yuxi realtime client connected: agent={} thread={}",
            config.agent_slug,
            config.thread_id or "new",
        )
        if not pending_interrupt_restore_started:
            pending_interrupt_restore_started = True
            try:
                event = await yuxi_client.restore_pending_interrupt()
            except Exception:
                pending_interrupt_restore_started = False
                raise
            if event:
                await worker.queue_frames([yuxi_agent_event_frame(event)])

    @worker.rtvi.event_handler("on_client_message")
    async def on_client_message(rtvi, message):
        if message.type == "yuxi.approval.answer":
            await worker.queue_frames([YuxiResumeFrame(answer=message.data)])
        elif message.type == "yuxi.media.attach":
            source = message.data.get("source") if isinstance(message.data, dict) else None
            yuxi_llm._media_source = source

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Yuxi realtime client disconnected")
        unregister_frame_broker(session_id)
        await yuxi_client.cancel_active_run()
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    try:
        await runner.add_workers(worker)
        await runner.run()
    finally:
        unregister_frame_broker(session_id)
        await yuxi_client.close()
