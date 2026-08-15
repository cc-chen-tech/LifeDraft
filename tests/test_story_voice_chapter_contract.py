from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.api.schemas import StoryVoiceReadingRequest
from src.database.models import SessionLocal, User, init_db
from src.services import story_voice_reading
from src.services.story_tts_provider import DeterministicTTSProvider, UnavailableTTSProvider
from src.services.story_voice_reading import StoryVoiceReadingService, normalize_text_hash
from src.services.story_voice_repository import StoryVoiceReadingRepository


def _user(session) -> int:
    user = User(
        private_id=f"chapter-{uuid4().hex[:20]}",
        public_id=f"C{uuid4().hex[:7]}",
        display_name="Chapter listener",
    )
    session.add(user)
    session.flush()
    return int(user.user_id)


def _request(text: str, *, source_type: str = "current_story") -> StoryVoiceReadingRequest:
    return StoryVoiceReadingRequest(
        context={
            "source_type": source_type,
            "game_id": 901,
            "week": 2,
            "round_number": 3,
            "stage": "event",
            "attempt_id": "chapter-contract",
            "day_index": 9,
            "story_date": "2026-08-15",
            "text_hash": normalize_text_hash(text),
            "text": text,
        },
        voice_id="warm_female",
        speed=1.25,
    )


def test_story_is_split_into_stable_nonempty_paragraphs() -> None:
    assert hasattr(story_voice_reading, "split_story_paragraphs")
    split = story_voice_reading.split_story_paragraphs

    assert split("第一段。\n\n  第二段第一行。\n第二段第二行。\n\n\n第三段。") == [
        "第一段。",
        "第二段第一行。\n第二段第二行。",
        "第三段。",
    ]


def test_reading_rejects_non_current_story_sources() -> None:
    init_db()
    session = SessionLocal()
    try:
        user_id = _user(session)
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session),
            provider=DeterministicTTSProvider(),
        )

        with pytest.raises(HTTPException) as error:
            service.request_reading(user_id, _request("历史故事。", source_type="history_round"))

        assert error.value.status_code == 422
        assert error.value.detail["error_code"] == "current_story_only"
    finally:
        session.rollback()
        session.close()


def test_provider_without_backend_audio_fails_without_browser_fallback() -> None:
    init_db()
    session = SessionLocal()
    try:
        user_id = _user(session)
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session),
            provider=UnavailableTTSProvider(),
        )

        response = service.request_reading(user_id, _request("只允许高质量语音。"))

        assert response.status == "failed"
        assert response.playback_mode == "unavailable"
        assert response.audio_url is None
        assert response.error_code == "tts_provider_unavailable"
    finally:
        session.rollback()
        session.close()


def test_voice_settings_persist_speed_and_default_auto_read_on() -> None:
    init_db()
    session = SessionLocal()
    try:
        user_id = _user(session)
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session),
            provider=DeterministicTTSProvider(),
        )

        initial = service.get_settings(user_id)
        updated = service.update_settings(user_id, "calm_male", False, 1.5)
        recovered = service.get_settings(user_id)

        assert initial.auto_read_enabled is True
        assert initial.selected_speed == 1.0
        assert updated.selected_speed == 1.5
        assert recovered.selected_speed == 1.5
    finally:
        session.rollback()
        session.close()


def test_reading_progress_is_scoped_to_owner_and_story_identity() -> None:
    init_db()
    session = SessionLocal()
    try:
        owner_id = _user(session)
        other_id = _user(session)
        repository = StoryVoiceReadingRepository(session)

        repository.upsert_progress(
            user_id=owner_id,
            game_id=901,
            day_index=9,
            story_date="2026-08-15",
            text_hash="story-hash",
            voice_id="warm_female",
            speed=1.0,
            paragraph_index=2,
            position_ms=1730,
            completed=False,
        )

        owned = repository.get_progress(
            owner_id, 901, 9, "story-hash", "warm_female", 1.0
        )
        hidden = repository.get_progress(
            other_id, 901, 9, "story-hash", "warm_female", 1.0
        )

        assert owned is not None
        assert owned.paragraph_index == 2
        assert owned.position_ms == 1730
        assert hidden is None
    finally:
        session.rollback()
        session.close()


def test_minimax_provider_never_falls_back_to_browser_speech(tmp_path) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_story_tts_provider import MiniMaxTTSProvider
    from src.services.story_tts_provider import TTSProviderUnavailableError

    provider = MiniMaxTTSProvider(
        config=MiniMaxConfig.from_env(
            {},
            voice_asset_dir=tmp_path / "voice",
        )
    )

    assert provider.metadata().playback_mode == "unavailable"
    with pytest.raises(TTSProviderUnavailableError):
        provider.synthesize(
            {"text": "高质量语音不可用。", "text_hash": "no-provider"},
            "warm_female",
            1.0,
        )
