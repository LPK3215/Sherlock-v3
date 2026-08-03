"""视觉模型能力预检和图片元数据单元测试。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from unittest.mock import patch, MagicMock

import yuxi.services.agent_run_service as agent_run_service
from yuxi.models.providers.cache import ModelInfo
from yuxi.services.input_message_service import build_chat_input_message


def _make_model_info(spec: str, *, input_modalities: list[str] | None = None) -> ModelInfo:
    return ModelInfo(
        provider_id=spec.split(":")[0],
        model_id=spec.split(":", 1)[1] if ":" in spec else spec,
        model_type="chat",
        display_name=spec,
        api_key="key",
        base_url="http://localhost",
        provider_type="openai",
        input_modalities=input_modalities or [],
    )


def test_check_model_vision_capability_passes_when_model_supports_image():
    info = _make_model_info("p:vision-model", input_modalities=["text", "image"])
    with patch("yuxi.services.agent_run_service.model_cache") as mock_cache:
        mock_cache.get_model_info.return_value = info
        agent_run_service._check_model_vision_capability("p:vision-model", has_image=True)


def test_check_model_vision_capability_skips_when_no_image():
    with patch("yuxi.services.agent_run_service.model_cache") as mock_cache:
        mock_cache.get_model_info.return_value = None
        agent_run_service._check_model_vision_capability("p:any-model", has_image=False)
        mock_cache.get_model_info.assert_not_called()


def test_check_model_vision_capability_raises_422_when_model_not_found():
    with patch("yuxi.services.agent_run_service.model_cache") as mock_cache:
        mock_cache.get_model_info.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            agent_run_service._check_model_vision_capability("p:unknown", has_image=True)
        assert exc_info.value.status_code == 422
        assert "无法获取模型信息" in exc_info.value.detail


def test_check_model_vision_capability_raises_422_when_model_has_no_image():
    info = _make_model_info("p:text-only", input_modalities=["text"])
    with patch("yuxi.services.agent_run_service.model_cache") as mock_cache:
        mock_cache.get_model_info.return_value = info
        with pytest.raises(HTTPException) as exc_info:
            agent_run_service._check_model_vision_capability("p:text-only", has_image=True)
        assert exc_info.value.status_code == 422
        assert "不支持图片输入" in exc_info.value.detail


def test_check_model_vision_capability_raises_422_when_modalities_empty():
    info = _make_model_info("p:no-modalities", input_modalities=[])
    with patch("yuxi.services.agent_run_service.model_cache") as mock_cache:
        mock_cache.get_model_info.return_value = info
        with pytest.raises(HTTPException) as exc_info:
            agent_run_service._check_model_vision_capability("p:no-modalities", has_image=True)
        assert exc_info.value.status_code == 422


def test_prepare_run_input_message_preserves_image_meta():
    image_meta = {
        "source": "camera",
        "captured_at": "2026-08-03T10:00:00+00:00",
        "width": 1280,
        "height": 720,
        "mime_type": "image/jpeg",
    }
    input_message = build_chat_input_message("看画面", "base64data")
    result = agent_run_service._prepare_run_input_message(
        run_type="chat",
        input_message=input_message,
        resume=None,
        request_id="req-1",
        model_spec="p:vision-model",
        meta={"source": "realtime", "image_meta": image_meta},
    )

    assert result.extra_metadata["image_meta"] == image_meta
    assert result.extra_metadata["source"] == "realtime"
    assert result.image_content == "base64data"
    assert result.message_type == "multimodal_image"


def test_prepare_run_input_message_omits_image_meta_when_absent():
    input_message = build_chat_input_message("hello")
    result = agent_run_service._prepare_run_input_message(
        run_type="chat",
        input_message=input_message,
        resume=None,
        request_id="req-1",
        model_spec="p:text-model",
        meta={"source": "realtime"},
    )

    assert "image_meta" not in result.extra_metadata


def test_model_info_round_trip_preserves_input_modalities():
    info = _make_model_info("p:vision", input_modalities=["text", "image", "video"])
    restored = ModelInfo.from_dict(info.to_dict())

    assert restored.input_modalities == ["text", "image", "video"]
    assert restored.spec == "p:vision"
