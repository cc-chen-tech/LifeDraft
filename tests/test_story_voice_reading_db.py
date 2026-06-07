"""Real DB integration tests for story voice reading save-read chains."""

from pathlib import Path
from uuid import uuid4
import wave

from src.database.models import (
    GeneratedVoiceAsset,
    SessionLocal,
    User,
    VoiceReadingJob,
    VoiceReadingSetting,
    init_db,
)
from src.services.story_voice_repository import StoryVoiceReadingRepository
from src.services.story_voice_reading import (
    StoryVoiceReadingService,
    build_deterministic_wav,
    normalize_text_hash,
)
from src.services.story_tts_provider import (
    BrowserSpeechTTSProvider,
    DeterministicTTSProvider,
    GeneratedSpeech,
    OpenAICompatibleTTSProvider,
    StoryTTSProviderMetadata,
)
from src.api.schemas import StoryVoiceReadingRequest


def test_voice_settings_save_read_chain_uses_real_database() -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Voice User")
        session.add(user)
        session.flush()

        repository = StoryVoiceReadingRepository(session)
        setting = repository.upsert_settings(
            user_id=int(user.user_id),
            selected_voice_color="warm_female",
            auto_read_enabled=True,
        )
        session.commit()

        loaded = (
            session.query(VoiceReadingSetting)
            .filter(VoiceReadingSetting.user_id == user.user_id)
            .one()
        )

        assert loaded.setting_id == setting.setting_id
        assert loaded.selected_voice_color == "warm_female"
        assert loaded.auto_read_enabled is True
    finally:
        session.rollback()
        session.close()


def test_voice_job_and_asset_reuse_by_text_hash_uses_real_database() -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Voice Asset")
        session.add(user)
        session.flush()

        repository = StoryVoiceReadingRepository(session)
        context = {
            "source_type": "current_story",
            "game_id": 101,
            "week": 3,
            "round_number": 2,
            "stage": "event",
            "attempt_id": "attempt-1",
            "text_hash": "hash-current-story",
            "text": "雨夜码头的旧账册被风吹开。",
        }
        asset = repository.create_asset(
            user_id=int(user.user_id),
            context=context,
            voice_id="warm_female",
            speed=1.0,
            provider="local",
            model="deterministic-v1",
            storage_path="/api/voice-reading/audio/hash-current-story.wav",
            duration_ms=1600,
            status="ready",
        )
        job = repository.create_job(
            user_id=int(user.user_id),
            context=context,
            voice_id="warm_female",
            speed=1.0,
            status="ready",
            asset_id=int(asset.asset_id),
        )
        session.commit()

        loaded_asset = repository.find_ready_asset(
            text_hash="hash-current-story",
            voice_id="warm_female",
            speed=1.0,
        )
        loaded_job = session.query(VoiceReadingJob).filter(VoiceReadingJob.job_id == job.job_id).one()

        assert loaded_asset is not None
        assert loaded_asset.asset_id == asset.asset_id
        assert loaded_job.asset_id == asset.asset_id
        assert loaded_job.context_json["game_id"] == 101
        assert loaded_job.context_json["stage"] == "event"
    finally:
        session.rollback()
        session.close()


def test_same_round_different_text_hash_does_not_reuse_old_audio() -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Voice Regen")
        session.add(user)
        session.flush()
        repository = StoryVoiceReadingRepository(session)

        old_context = {
            "source_type": "current_story",
            "game_id": 202,
            "week": 5,
            "round_number": 1,
            "stage": "event",
            "attempt_id": "old",
            "text_hash": "old-hash",
            "text": "旧版本故事。",
        }
        repository.create_asset(
            user_id=int(user.user_id),
            context=old_context,
            voice_id="calm_male",
            speed=1.0,
            provider="local",
            model="deterministic-v1",
            storage_path="/api/voice-reading/audio/old.wav",
            duration_ms=900,
            status="ready",
        )
        session.commit()

        assert repository.find_ready_asset("old-hash", "calm_male", 1.0) is not None
        assert repository.find_ready_asset("new-hash", "calm_male", 1.0) is None
        assert session.query(GeneratedVoiceAsset).count() >= 1
    finally:
        session.rollback()
        session.close()


def test_provider_model_identity_prevents_wrong_audio_reuse() -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Voice Provider")
        session.add(user)
        session.flush()
        repository = StoryVoiceReadingRepository(session)
        context = {
            "source_type": "current_story",
            "game_id": 303,
            "week": 2,
            "round_number": 1,
            "stage": "event",
            "attempt_id": "provider-a",
            "text_hash": "same-story-hash",
            "text": "同一段故事应该按 provider 和 model 区分音频。",
        }
        repository.create_asset(
            user_id=int(user.user_id),
            context=context,
            voice_id="warm_female",
            speed=1.0,
            provider="local",
            model="deterministic-v1",
            storage_path="/api/voice-reading/audio/local.wav",
            duration_ms=2400,
            status="ready",
        )
        session.commit()

        assert repository.find_ready_asset(
            "same-story-hash",
            "warm_female",
            1.0,
            provider="local",
            model="deterministic-v1",
        ) is not None
        assert repository.find_ready_asset(
            "same-story-hash",
            "warm_female",
            1.0,
            provider="openai",
            model="gpt-4o-mini-tts",
        ) is None
    finally:
        session.rollback()
        session.close()


def test_browser_fallback_request_saves_job_without_wav_asset() -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Voice Browser")
        session.add(user)
        session.flush()
        repository = StoryVoiceReadingRepository(session)
        service = StoryVoiceReadingService(repository, provider=BrowserSpeechTTSProvider())
        text = "浏览器应该朗读这段真实故事文字。"
        text_hash = normalize_text_hash(text)
        response = service.request_reading(
            int(user.user_id),
            StoryVoiceReadingRequest(
                context={
                    "source_type": "current_story",
                    "game_id": 404,
                    "week": 1,
                    "round_number": 1,
                    "stage": "event",
                    "attempt_id": "browser",
                    "text_hash": text_hash,
                    "text": text,
                },
                voice_id="warm_female",
                speed=1.0,
                auto_play=True,
            ),
        )
        session.commit()

        assert response.playback_mode == "browser_speech"
        assert response.audio_url is None
        assert response.provider == "browser"
        assert response.asset_id is None
        assert session.query(GeneratedVoiceAsset).filter_by(text_hash=text_hash).count() == 0
        assert session.query(VoiceReadingJob).filter_by(job_id=response.job_id).one().status == "ready"
    finally:
        session.rollback()
        session.close()


def test_provider_backed_request_saves_and_reuses_asset() -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Voice Local")
        session.add(user)
        session.flush()
        repository = StoryVoiceReadingRepository(session)
        service = StoryVoiceReadingService(repository, provider=DeterministicTTSProvider())
        text = "后端 TTS provider 应该保存并复用这一段故事音频。"
        text_hash = normalize_text_hash(text)
        request = StoryVoiceReadingRequest(
            context={
                "source_type": "current_story",
                "game_id": 505,
                "week": 2,
                "round_number": 2,
                "stage": "event",
                "attempt_id": "local",
                "text_hash": text_hash,
                "text": text,
            },
            voice_id="warm_female",
            speed=1.0,
            auto_play=True,
        )

        first = service.request_reading(int(user.user_id), request)
        second = service.request_reading(int(user.user_id), request)
        session.commit()

        assert first.playback_mode == "audio"
        assert first.audio_url is not None
        assert first.provider == "local"
        assert first.model == "deterministic-v1"
        assert second.asset_id == first.asset_id
        assert (
            session.query(GeneratedVoiceAsset)
            .filter_by(text_hash=text_hash, user_id=int(user.user_id))
            .count()
            == 1
        )
        assert (
            session.query(VoiceReadingJob)
            .filter_by(text_hash=text_hash, user_id=int(user.user_id))
            .count()
            == 2
        )
    finally:
        session.rollback()
        session.close()


def test_cached_minimax_mp3_asset_reports_mpeg_media_type() -> None:
    class CachedMiniMaxProvider:
        provider = "minimax"
        model = "speech-02-turbo"

        def metadata(self) -> StoryTTSProviderMetadata:
            return StoryTTSProviderMetadata(
                provider=self.provider,
                model=self.model,
                playback_mode="audio",
                media_type="audio/mpeg",
                available=True,
                backend_audio_enabled=True,
            )

        def synthesize(self, context, voice_id, speed) -> GeneratedSpeech:
            raise AssertionError("cached mp3 asset should be reused without synthesis")

    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Voice MP3")
        session.add(user)
        session.flush()
        repository = StoryVoiceReadingRepository(session)
        text = "缓存的 MiniMax mp3 朗读资产应该按真实格式返回。"
        text_hash = normalize_text_hash(text)
        context = {
            "source_type": "current_story",
            "game_id": 606,
            "week": 1,
            "round_number": 1,
            "stage": "event",
            "attempt_id": "mp3-cache",
            "text_hash": text_hash,
            "text": text,
        }
        repository.create_asset(
            user_id=int(user.user_id),
            context=context,
            voice_id="warm_female",
            speed=1.0,
            provider="minimax",
            model="speech-02-turbo",
            storage_path="/api/voice-reading/audio/minimax-cache.mp3",
            duration_ms=2200,
            status="ready",
        )
        session.commit()

        service = StoryVoiceReadingService(repository, provider=CachedMiniMaxProvider())
        request = StoryVoiceReadingRequest(
            context=context,
            voice_id="warm_female",
            speed=1.0,
            auto_play=True,
        )

        response = service.request_reading(int(user.user_id), request)
        job = service.get_job(int(user.user_id), int(response.job_id))

        assert response.playback_mode == "audio"
        assert response.audio_url is not None and response.audio_url.endswith(".mp3")
        assert response.media_type == "audio/mpeg"
        assert job.media_type == "audio/mpeg"
    finally:
        session.rollback()
        session.close()


def test_provider_backed_request_does_not_reuse_other_users_voice_asset() -> None:
    init_db()
    session = SessionLocal()
    try:
        owner = User(
            private_id=f"priv_{uuid4().hex[:16]}",
            public_id=f"pub_{uuid4().hex[:6]}",
            display_name="Voice Owner",
        )
        requester = User(
            private_id=f"priv_{uuid4().hex[:16]}",
            public_id=f"pub_{uuid4().hex[:6]}",
            display_name="Voice Requester",
        )
        session.add_all([owner, requester])
        session.flush()
        repository = StoryVoiceReadingRepository(session)
        service = StoryVoiceReadingService(repository, provider=DeterministicTTSProvider())
        text = "同一段故事也不能跨用户复用朗读资产。"
        text_hash = normalize_text_hash(text)
        context = {
            "source_type": "current_story",
            "game_id": 707,
            "week": 1,
            "round_number": 1,
            "stage": "event",
            "attempt_id": "cross-user",
            "text_hash": text_hash,
            "text": text,
        }
        owner_asset = repository.create_asset(
            user_id=int(owner.user_id),
            context=context,
            voice_id="warm_female",
            speed=1.0,
            provider="local",
            model="deterministic-v1",
            storage_path="/api/voice-reading/audio/owner-only.wav",
            duration_ms=2200,
            status="ready",
        )
        session.commit()

        response = service.request_reading(
            int(requester.user_id),
            StoryVoiceReadingRequest(
                context=context,
                voice_id="warm_female",
                speed=1.0,
                auto_play=True,
            ),
        )
        session.commit()

        assert response.playback_mode == "audio"
        assert response.asset_id != int(owner_asset.asset_id)
        assert response.audio_url != "/api/voice-reading/audio/owner-only.wav"
        assert (
            session.query(GeneratedVoiceAsset)
            .filter_by(text_hash=text_hash, user_id=int(requester.user_id))
            .count()
            == 1
        )
    finally:
        session.rollback()
        session.close()


def test_openai_compatible_provider_keeps_generated_files_inside_asset_dir(tmp_path: Path) -> None:
    class ExistingFileOpenAIProvider(OpenAICompatibleTTSProvider):
        def _request_speech(self, text: str, voice_id: str, speed: float, output_path: Path) -> None:
            raise AssertionError("fixture file should be reused without network access")

    text_hash = "safe-story-hash"
    expected_file = tmp_path / "safe-story-hash-warm_female-openai-model-with-path.wav"
    with wave.open(str(expected_file), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(b"\x00\x00" * 16)

    provider = ExistingFileOpenAIProvider(
        api_key="test-key",
        model="../model/with:path",
        asset_dir=tmp_path,
    )
    speech = provider.synthesize(
        {
            "text_hash": text_hash,
            "text": "路径字符不应该逃出语音资产目录。",
        },
        "warm_female",
        1.0,
    )

    assert speech.storage_path == "/api/voice-reading/audio/safe-story-hash-warm_female-openai-model-with-path.wav"
    assert expected_file.is_file()
    assert not (tmp_path.parent / "model").exists()


def test_deterministic_voice_audio_bytes_are_playable_wav() -> None:
    audio = build_deterministic_wav("fixture-audio-hash", "warm_female")

    assert audio[:4] == b"RIFF"
    assert audio[8:12] == b"WAVE"
    assert audio[12:16] == b"fmt "
    assert audio[36:40] == b"data"
    assert len(audio) > 4_000


def test_deterministic_voice_audio_duration_leaves_room_for_browser_controls() -> None:
    audio = build_deterministic_wav("fixture-audio-hash", "warm_female")

    import wave
    from io import BytesIO

    with wave.open(BytesIO(audio), "rb") as wav:
        duration_seconds = wav.getnframes() / wav.getframerate()

    assert duration_seconds >= 8.0
