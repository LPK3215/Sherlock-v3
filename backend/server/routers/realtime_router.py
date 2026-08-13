"""Sherlock native realtime session and WebRTC endpoints."""

from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from pipecat.transports.smallwebrtc.request_handler import (
    IceCandidate,
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
)
from server.utils.auth_middleware import get_db, get_required_user
from yuxi.repositories.agent_repository import REALTIME_AGENT_SLUG
from yuxi.repositories.conversation_repository import ConversationRepository
from yuxi.realtime import realtime_session_manager
from yuxi.realtime.pipeline import capture_realtime_frame
from yuxi.services.conversation_service import create_thread_view

router = APIRouter(prefix="/realtime", tags=["realtime"])


class RealtimeStartRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    agent_slug: str = REALTIME_AGENT_SLUG
    thread_id: str | None = None
    enable_default_ice_servers: bool = Field(default=True, alias="enableDefaultIceServers")


class RealtimeOfferRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sdp: str
    type: str
    pc_id: str | None = None
    restart_pc: bool | None = None
    request_data: dict | None = Field(default=None, alias="requestData")


class RealtimeIceCandidate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    candidate: str
    sdp_mid: str = Field(alias="sdpMid")
    sdp_mline_index: int = Field(alias="sdpMLineIndex")


class RealtimeIceRequest(BaseModel):
    pc_id: str
    candidates: list[RealtimeIceCandidate]


class CaptureFrameRequest(BaseModel):
    source: str
    wait_fresh_ms: int = 3000


@router.post("/start")
async def start_realtime_session(
    payload: RealtimeStartRequest,
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    uid = str(user.uid)
    thread_id = payload.thread_id
    if thread_id:
        conversation = await ConversationRepository(db).get_conversation_by_thread_id(thread_id)
        if not conversation or conversation.uid != uid or conversation.status == "deleted":
            raise HTTPException(status_code=404, detail="对话线程不存在")
        if conversation.agent_id != payload.agent_slug:
            raise HTTPException(status_code=409, detail="对话线程与 Agent 不匹配")
    else:
        thread = await create_thread_view(
            agent_slug=payload.agent_slug,
            title="Sherlock 实时对话",
            metadata={"source": "realtime", "channel": "voice"},
            db=db,
            current_uid=uid,
        )
        thread_id = str(thread["id"])

    session = realtime_session_manager.create_session(
        uid=uid,
        agent_slug=payload.agent_slug,
        thread_id=thread_id,
    )
    result = {"sessionId": session.session_id, "threadId": session.thread_id}
    if payload.enable_default_ice_servers:
        result["iceConfig"] = {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
    return result


@router.post("/sessions/{session_id}/offer")
async def realtime_offer(session_id: str, payload: RealtimeOfferRequest, user=Depends(get_required_user)):
    try:
        return await realtime_session_manager.offer(
            session_id,
            SmallWebRTCRequest(
                sdp=payload.sdp,
                type=payload.type,
                pc_id=payload.pc_id,
                restart_pc=payload.restart_pc,
                request_data=payload.request_data,
            ),
            uid=str(user.uid),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.patch("/sessions/{session_id}/offer")
async def realtime_ice_candidate(session_id: str, payload: RealtimeIceRequest, user=Depends(get_required_user)):
    request = SmallWebRTCPatchRequest(
        pc_id=payload.pc_id,
        candidates=[
            IceCandidate(
                candidate=candidate.candidate,
                sdp_mid=candidate.sdp_mid,
                sdp_mline_index=candidate.sdp_mline_index,
            )
            for candidate in payload.candidates
        ],
    )
    try:
        await realtime_session_manager.add_ice_candidates(session_id, request, uid=str(user.uid))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"status": "success"}


@router.post("/internal/sessions/{session_id}/frames/capture", include_in_schema=False)
async def capture_frame(
    session_id: str,
    payload: CaptureFrameRequest,
    authorization: str | None = Header(default=None),
    x_sherlock_uid: str | None = Header(default=None),
):
    expected_token = os.getenv("SHERLOCK_REALTIME_INTERNAL_TOKEN")
    supplied_token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected_token or not secrets.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=401, detail="invalid Sherlock internal credential")
    if payload.source not in {"camera", "screen"}:
        raise HTTPException(status_code=422, detail="source must be camera or screen")
    try:
        return await capture_realtime_frame(
            session_id,
            str(x_sherlock_uid or ""),
            payload.source,
            payload.wait_fresh_ms,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="timed out waiting for a fresh frame") from exc
