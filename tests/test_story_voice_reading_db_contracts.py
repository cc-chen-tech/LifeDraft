from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.api.schemas import StoryVoiceReadingRequest
from src.database.models import GeneratedVoiceAsset, SessionLocal, User, VoiceReadingJob, init_db
from src.services.story_tts_provider import DeterministicTTSProvider, UnavailableTTSProvider
from src.services.story_voice_reading import (
    StoryVoiceReadingService,
    media_type_for_voice_asset,
    normalize_text_hash,
)
from src.services.story_voice_repository import StoryVoiceReadingRepository


def _add_user(session: Session) -> int:
    suffix = uuid4().hex[:12]
    user = User(
        private_id=f"maintained-voice-{suffix}",
        public_id=f"V{suffix[:7]}",
        display_name="Maintained Voice Contract",
    )
    session.add(user)
    session.flush()
    return int(user.user_id)


def _reading_request(text: str, **context_overrides: object) -> StoryVoiceReadingRequest:
    context = {
        "source_type": "current_story",
        "game_id": 731,
        "week": 4,
        "round_number": 2,
        "stage": "event",
        "attempt_id": "voice-contract-attempt",
        "text_hash": normalize_text_hash(text),
        "text": text,
    }
    context.update(context_overrides)
    return StoryVoiceReadingRequest(context=context)


def test_voice_settings_persist_through_service_with_real_database() -> None:
    init_db()
    session = SessionLocal()
    try:
        user_id = _add_user(session)
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session),
            provider=DeterministicTTSProvider(),
        )

        initial = service.get_settings(user_id)
        updated = service.update_settings(user_id, "calm_male", True)
        recovered = service.get_settings(user_id)

        assert initial.selected_voice_color == "warm_female"
        assert initial.auto_read_enabled is True
        assert initial.playback_mode == "audio"
        assert updated.selected_voice_color == "calm_male"
        assert updated.auto_read_enabled is True
        assert recovered.tts_model == "deterministic-v1"
        assert session.query(GeneratedVoiceAsset).filter_by(user_id=user_id).count() == 0
    finally:
        session.rollback()
        session.close()


def test_unavailable_provider_persists_failed_job_without_audio_asset() -> None:
    init_db()
    session = SessionLocal()
    try:
        user_id = _add_user(session)
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session),
            provider=UnavailableTTSProvider(),
        )

        response = service.request_reading(user_id, _reading_request("浏览器朗读也必须保留可恢复的任务状态。"))
        recovered = service.get_job(user_id, response.job_id)

        assert response.status == "failed"
        assert response.audio_url is None
        assert response.asset_id is None
        assert response.playback_mode == "unavailable"
        assert response.provider == "unavailable"
        assert response.model == "unavailable"
        assert recovered.job_id == response.job_id
        assert recovered.playback_mode == "unavailable"
        assert recovered.media_type is None
        assert session.query(GeneratedVoiceAsset).filter_by(user_id=user_id).count() == 0
        assert session.query(VoiceReadingJob).filter_by(user_id=user_id).count() == 1
    finally:
        session.rollback()
        session.close()


def test_deterministic_reading_creates_then_reuses_owned_audio_asset() -> None:
    init_db()
    session = SessionLocal()
    try:
        user_id = _add_user(session)
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session),
            provider=DeterministicTTSProvider(),
        )
        request = _reading_request("确定性朗读资产必须按用户和内容稳定复用。")

        generated = service.request_reading(user_id, request)
        reused = service.request_reading(user_id, request)
        recovered = service.process_job(user_id, generated.job_id)

        assert generated.status == "queued"
        assert reused.job_id == generated.job_id
        assert recovered.provider == "local"
        assert recovered.model == "deterministic-v1"
        assert recovered.audio_url == "/api/voice-reading/audio/" + normalize_text_hash(request.context.text) + "-warm_female.wav"
        assert recovered.duration_ms == 8_000
        assert recovered.media_type == "audio/wav"
        assert recovered.playback_mode == "audio"
        assert session.query(GeneratedVoiceAsset).filter_by(user_id=user_id).count() == 1
        assert session.query(VoiceReadingJob).filter_by(user_id=user_id).count() == 1
    finally:
        session.rollback()
        session.close()


def test_reading_context_rejects_missing_identity_and_text_hash_mismatch() -> None:
    init_db()
    session = SessionLocal()
    try:
        user_id = _add_user(session)
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session),
            provider=UnavailableTTSProvider(),
        )
        text = "阅读上下文的身份和文本哈希必须匹配。"

        with pytest.raises(HTTPException) as missing_identity:
            service.request_reading(
                user_id,
                _reading_request(text, week=None, round_number=None, stage=None),
            )
        with pytest.raises(HTTPException) as mismatched_hash:
            service.request_reading(user_id, _reading_request(text, text_hash="not-the-text-hash"))

        assert missing_identity.value.status_code == 422
        assert missing_identity.value.detail["error_code"] == "missing_context_identity"
        assert mismatched_hash.value.status_code == 422
        assert mismatched_hash.value.detail["error_code"] == "text_hash_mismatch"
        assert session.query(VoiceReadingJob).filter_by(user_id=user_id).count() == 0
    finally:
        session.rollback()
        session.close()


def test_voice_asset_media_types_are_derived_from_stored_paths() -> None:
    assert media_type_for_voice_asset("/api/voice-reading/audio/narration.mp3") == "audio/mpeg"
    assert media_type_for_voice_asset("/api/voice-reading/audio/narration.m4a?token=current") == "audio/mp4"
    assert media_type_for_voice_asset("/api/voice-reading/audio/narration.ogg") == "audio/ogg"
    assert media_type_for_voice_asset("/api/voice-reading/audio/narration.wav") == "audio/wav"
