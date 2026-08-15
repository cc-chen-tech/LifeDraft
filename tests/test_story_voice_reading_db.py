"""Real DB integration tests for story voice reading save-read chains."""

from uuid import uuid4
import wave

from sqlalchemy import create_engine, inspect, text

from src.database import models as database_models
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
    DeterministicTTSProvider,
    GeneratedSpeech,
    StoryTTSProviderMetadata,
    UnavailableTTSProvider,
)
from src.api.schemas import StoryVoiceReadingRequest


def test_asset_version_schema_migration_is_additive_and_idempotent(tmp_path, monkeypatch) -> None:
    migration_engine = create_engine(f"sqlite:///{tmp_path / 'legacy-voice.db'}")
    with migration_engine.begin() as connection:
        connection.execute(text("CREATE TABLE generated_voice_assets (asset_id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE voice_reading_jobs (job_id INTEGER PRIMARY KEY)"))

    monkeypatch.setattr(database_models, "engine", migration_engine)
    database_models._ensure_legacy_columns()
    database_models._ensure_legacy_columns()

    inspector = inspect(migration_engine)
    asset_columns = {column["name"] for column in inspector.get_columns("generated_voice_assets")}
    job_columns = {column["name"] for column in inspector.get_columns("voice_reading_jobs")}
    with migration_engine.begin() as connection:
        connection.execute(text("INSERT INTO generated_voice_assets (asset_id) VALUES (1)"))
        connection.execute(text("INSERT INTO voice_reading_jobs (job_id) VALUES (1)"))
        asset_version = connection.execute(
            text("SELECT asset_version FROM generated_voice_assets WHERE asset_id = 1")
        ).scalar_one()
        job_version = connection.execute(
            text("SELECT asset_version FROM voice_reading_jobs WHERE job_id = 1")
        ).scalar_one()

    assert "asset_version" in asset_columns
    assert "asset_version" in job_columns
    assert asset_version == 1
    assert job_version == 1


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


def test_voice_settings_use_env_auto_read_default_for_new_user(monkeypatch) -> None:
    init_db()
    monkeypatch.setenv("STORY_TTS_AUTO_READ_DEFAULT_ENABLED", "true")
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Voice Default")
        session.add(user)
        session.flush()

        response = StoryVoiceReadingService(StoryVoiceReadingRepository(session)).get_settings(
            int(user.user_id)
        )

        assert response.auto_read_enabled is True
        assert session.query(VoiceReadingSetting).filter_by(user_id=int(user.user_id)).count() == 0
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


def test_v1_voice_assets_are_retained_but_excluded_from_v2_reuse() -> None:
    init_db()
    session = SessionLocal()
    try:
        user = User(
            private_id=f"priv_{uuid4().hex[:16]}",
            public_id=f"pub_{uuid4().hex[:6]}",
            display_name="Voice Cache Version",
        )
        session.add(user)
        session.flush()
        repository = StoryVoiceReadingRepository(session)
        context = {
            "source_type": "current_story",
            "game_id": 911,
            "week": 1,
            "round_number": 1,
            "stage": "event",
            "attempt_id": "legacy-v1",
            "text_hash": "v1-cache-key",
            "text": "保留旧资产但不能复用。",
        }
        legacy_asset = GeneratedVoiceAsset(
            user_id=int(user.user_id),
            source_type="current_story",
            context_json=context,
            text_hash="v1-cache-key",
            voice_id="warm_female",
            speed=1.0,
            provider="minimax",
            model="speech-02-turbo",
            storage_path="/api/voice-reading/audio/legacy-v1.mp3",
            duration_ms=800,
            status="ready",
            asset_version=1,
        )
        session.add(legacy_asset)
        session.flush()

        fresh_asset = repository.create_asset(
            user_id=int(user.user_id),
            context=context,
            voice_id="warm_female",
            speed=1.0,
            provider="minimax",
            model="speech-02-turbo",
            storage_path="/api/voice-reading/audio/fresh-v2.mp3",
            duration_ms=800,
            status="ready",
        )

        reusable = repository.find_ready_asset(
            "v1-cache-key",
            "warm_female",
            1.0,
            provider="minimax",
            model="speech-02-turbo",
            user_id=int(user.user_id),
        )

        assert legacy_asset.asset_version == 1
        assert fresh_asset.asset_version == 2
        assert reusable is not None
        assert reusable.asset_id == fresh_asset.asset_id
    finally:
        session.rollback()
        session.close()


def test_v2_request_deduplication_isolated_from_legacy_jobs() -> None:
    init_db()
    session = SessionLocal()
    try:
        user = User(
            private_id=f"priv_{uuid4().hex[:16]}",
            public_id=f"pub_{uuid4().hex[:6]}",
            display_name="Voice Job Cache Version",
        )
        session.add(user)
        session.flush()
        context = {
            "source_type": "current_story",
            "game_id": 912,
            "week": 1,
            "round_number": 1,
            "stage": "event",
            "attempt_id": "legacy-v1-job",
            "text_hash": normalize_text_hash("旧任务不得阻断 v2 音频生成。"),
            "text": "旧任务不得阻断 v2 音频生成。",
        }
        legacy_dedupe_key = normalize_text_hash(
            ":".join(
                [
                    str(user.user_id),
                    str(context["text_hash"]),
                    "warm_female",
                    "1.0",
                    "local",
                    "deterministic-v1",
                ]
            )
        )
        legacy_job = VoiceReadingJob(
            user_id=int(user.user_id),
            context_json=context,
            text_hash=str(context["text_hash"]),
            voice_id="warm_female",
            speed=1.0,
            asset_version=1,
            status="ready",
            dedupe_key=legacy_dedupe_key,
        )
        session.add(legacy_job)
        session.flush()

        response = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session), provider=DeterministicTTSProvider()
        ).request_reading(
            int(user.user_id),
            StoryVoiceReadingRequest(
                context=context,
                voice_id="warm_female",
                speed=1.0,
            ),
        )
        created = session.query(VoiceReadingJob).filter_by(job_id=response.job_id).one()

        assert created.job_id != legacy_job.job_id
        assert created.asset_version == 2
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


def test_unavailable_provider_saves_failed_job_without_audio_asset() -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Voice Browser")
        session.add(user)
        session.flush()
        repository = StoryVoiceReadingRepository(session)
        service = StoryVoiceReadingService(repository, provider=UnavailableTTSProvider())
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

        assert response.playback_mode == "unavailable"
        assert response.audio_url is None
        assert response.provider == "unavailable"
        assert response.asset_id is None
        assert session.query(GeneratedVoiceAsset).filter_by(text_hash=text_hash).count() == 0
        assert response.error_code == "tts_provider_unavailable"
        assert session.query(VoiceReadingJob).filter_by(job_id=response.job_id).one().status == "failed"
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
        text = f"后端 TTS provider 应该保存并复用这一段故事音频。{uuid4().hex}"
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
        ready = service.process_job(int(user.user_id), first.job_id)
        session.commit()

        assert first.status == "queued"
        assert second.job_id == first.job_id
        assert ready.playback_mode == "audio"
        assert ready.audio_url is not None
        assert ready.provider == "local"
        assert ready.model == "deterministic-v1"
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
            == 1
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
        job = service.process_job(int(user.user_id), int(response.job_id))

        assert response.status == "queued"
        assert job.audio_url is not None and job.audio_url.endswith(".mp3")
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
        ready = service.process_job(int(requester.user_id), response.job_id)
        session.commit()

        assert ready.playback_mode == "audio"
        assert ready.asset_id != int(owner_asset.asset_id)
        assert ready.audio_url != "/api/voice-reading/audio/owner-only.wav"
        assert (
            session.query(GeneratedVoiceAsset)
            .filter_by(text_hash=text_hash, user_id=int(requester.user_id))
            .count()
            == 1
        )
    finally:
        session.rollback()
        session.close()


def test_cached_mp3_voice_asset_returns_mpeg_media_type() -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Voice MP3")
        session.add(user)
        session.flush()
        repository = StoryVoiceReadingRepository(session)
        service = StoryVoiceReadingService(repository, provider=DeterministicTTSProvider())
        text = f"MiniMax 生成的 MP3 缓存音频应该保持正确媒体类型。{uuid4().hex}"
        text_hash = normalize_text_hash(text)
        context = {
            "source_type": "current_story",
            "game_id": 606,
            "week": 3,
            "round_number": 1,
            "stage": "event",
            "attempt_id": "minimax-cache",
            "text_hash": text_hash,
            "text": text,
        }
        repository.create_asset(
            user_id=int(user.user_id),
            context=context,
            voice_id="warm_female",
            speed=1.0,
            provider="local",
            model="deterministic-v1",
            storage_path="/api/voice-reading/audio/minimax-story.mp3",
            duration_ms=3200,
            status="ready",
        )
        session.commit()

        response = service.request_reading(
            int(user.user_id),
            StoryVoiceReadingRequest(
                context=context,
                voice_id="warm_female",
                speed=1.0,
                auto_play=True,
            ),
        )

        ready = service.process_job(int(user.user_id), response.job_id)

        assert ready.playback_mode == "audio"
        assert ready.audio_url == "/api/voice-reading/audio/minimax-story.mp3"
        assert ready.media_type == "audio/mpeg"
    finally:
        session.rollback()
        session.close()


def test_job_response_for_mp3_voice_asset_returns_mpeg_media_type() -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Voice Job MP3")
        session.add(user)
        session.flush()
        repository = StoryVoiceReadingRepository(session)
        service = StoryVoiceReadingService(repository, provider=DeterministicTTSProvider())
        context = {
            "source_type": "current_story",
            "game_id": 707,
            "week": 4,
            "round_number": 2,
            "stage": "event",
            "attempt_id": "minimax-job",
            "text_hash": "minimax-job-hash",
            "text": "任务恢复接口也应该报告 MP3 的真实媒体类型。",
        }
        asset = repository.create_asset(
            user_id=int(user.user_id),
            context=context,
            voice_id="calm_male",
            speed=1.0,
            provider="minimax",
            model="speech-02-turbo",
            storage_path="/api/voice-reading/audio/minimax-job.mp3",
            duration_ms=4100,
            status="ready",
        )
        job = repository.create_job(
            user_id=int(user.user_id),
            context=context,
            voice_id="calm_male",
            speed=1.0,
            status="ready",
            asset_id=int(asset.asset_id),
        )
        session.commit()

        response = service.get_job(int(user.user_id), int(job.job_id))

        assert response.playback_mode == "audio"
        assert response.audio_url == "/api/voice-reading/audio/minimax-job.mp3"
        assert response.media_type == "audio/mpeg"
    finally:
        session.rollback()
        session.close()


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
