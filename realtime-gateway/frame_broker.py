"""Per-session on-demand camera and screen frame capture."""

from __future__ import annotations

import asyncio
import base64
import io
import os
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from PIL import Image
from pipecat.frames.frames import UserImageRawFrame, UserImageRequestFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pydantic import BaseModel

router = APIRouter(prefix="/internal/realtime", include_in_schema=False)
_brokers: dict[str, "FrameBroker"] = {}


class CaptureRequest(BaseModel):
    source: Literal["camera", "screen"]
    wait_fresh_ms: int = 2000


class FrameBroker(FrameProcessor):
    def __init__(
        self,
        *,
        session_id: str,
        uid: str,
        request_video_keyframe: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        super().__init__(name=f"FrameBroker({session_id})")
        self.session_id = session_id
        self.uid = uid
        self.user_id = ""
        self._request_video_keyframe = request_video_keyframe
        self._pending: dict[int, asyncio.Future[UserImageRawFrame]] = {}

    async def capture(self, source: str, wait_fresh_ms: int) -> dict:
        if not self.user_id:
            raise RuntimeError("realtime media client is not connected")
        video_source = "screenVideo" if source == "screen" else "camera"
        request = UserImageRequestFrame(
            user_id=self.user_id,
            append_to_context=False,
            video_source=video_source,
        )
        future = asyncio.get_running_loop().create_future()
        self._pending[request.id] = future
        await self.push_frame(request, FrameDirection.UPSTREAM)
        if source == "screen":
            # The input transport starts screen reception in a background task.
            # Let it enable the receiver before requesting the keyframe.
            await asyncio.sleep(0)
        if self._request_video_keyframe:
            await self._request_video_keyframe(source)
        try:
            frame = await asyncio.wait_for(
                future, timeout=max(100, min(wait_fresh_ms, 5000)) / 1000
            )
        finally:
            self._pending.pop(request.id, None)

        image = Image.frombytes(frame.format or "RGB", frame.size, frame.image)
        image.thumbnail((1280, 1280))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=82, optimize=True)
        return {
            "session_id": self.session_id,
            "source": source,
            "mime_type": "image/jpeg",
            "width": image.width,
            "height": image.height,
            "captured_at": datetime.now(UTC).isoformat(),
            "data_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
        }

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, UserImageRawFrame) and frame.request:
            future = self._pending.get(frame.request.id)
            if future and not future.done():
                future.set_result(frame)
                return
        await self.push_frame(frame, direction)


def register_frame_broker(broker: FrameBroker) -> None:
    _brokers[broker.session_id] = broker


def unregister_frame_broker(session_id: str) -> None:
    _brokers.pop(session_id, None)


@router.post("/sessions/{session_id}/frames/capture")
async def capture_frame(
    session_id: str,
    request: CaptureRequest,
    authorization: str | None = Header(default=None),
    x_yuxi_uid: str | None = Header(default=None),
):
    expected_token = os.getenv("REALTIME_GATEWAY_INTERNAL_TOKEN")
    supplied_token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected_token or not secrets.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=401, detail="invalid realtime gateway credential")

    broker = _brokers.get(session_id)
    if not broker:
        raise HTTPException(status_code=404, detail="realtime session is not active")
    if not x_yuxi_uid or not secrets.compare_digest(x_yuxi_uid, broker.uid):
        raise HTTPException(status_code=403, detail="realtime session user mismatch")
    try:
        return await broker.capture(request.source, request.wait_fresh_ms)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="timed out waiting for a fresh frame") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
