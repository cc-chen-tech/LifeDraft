"""Durable narration regressions, using independent file SQLite connections."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.schemas import StoryVoiceReadingRequest
from src.database.models import Base, User, VoiceReadingJob
from src.services.story_tts_provider import DeterministicTTSProvider, GeneratedSpeech, ParagraphCue
from src.services.story_voice_reading import StoryVoiceReadingService, normalize_text_hash
from src.services.story_voice_repository import StoryVoiceReadingRepository


@pytest.fixture
def voice_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'voice.db'}", connect_args={"timeout": 0.05})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(
            User(
                user_id=1,
                private_id="voice-recovery",
                public_id="voice-rec",
                display_name="Listener",
            )
        )
        db.commit()
    yield factory
    engine.dispose()


def request():
    text = "第一段已经完成。\n\n第二段供应商暂时失败。\n\n第三段还没有执行。"
    return StoryVoiceReadingRequest(
        context={
            "source_type": "current_story",
            "game_id": 77,
            "week": 1,
            "round_number": 1,
            "stage": "event",
            "text_hash": normalize_text_hash(text),
            "text": text,
        },
        voice_id="clear_neutral",
        speed=1.0,
    )


class SceneProvider(DeterministicTTSProvider):
    fail_scene = True
    fail_assembly = False

    def __init__(self):
        self.calls = []
        self.during_scene = None

    def synthesize_scene(self, context, voice_id, speed, on_progress=None):
        self.calls.append(context["text"])
        if self.during_scene:
            self.during_scene()
        if self.fail_scene and context["text"].startswith("第二段"):
            raise RuntimeError("scene unavailable")
        return GeneratedSpeech(
            storage_path=f"/api/voice-reading/audio/{context['text_hash']}.wav",
            duration_ms=1000,
            provider=self.provider,
            model=self.model,
            media_type="audio/wav",
            playback_mode="audio",
            paragraph_cues=(ParagraphCue(0, 0, 1000),),
        )

    def assemble_scenes(self, paths, context, voice_id, speed, on_progress=None):
        if self.fail_assembly:
            raise RuntimeError("assembly unavailable")
        return super().synthesize(context, voice_id, speed, on_progress=on_progress)


def test_get_processing_job_does_not_write_under_an_independent_writer_lock(voice_db):
    with voice_db() as setup:
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(setup), provider=SceneProvider()
        )
        queued = service.request_reading(1, request())
        job = setup.get(VoiceReadingJob, queued.job_id)
        job.status = "processing"
        setup.commit()
    with voice_db().get_bind().connect() as writer:
        writer.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            with voice_db() as reader:
                result = StoryVoiceReadingService(
                    StoryVoiceReadingRepository(reader), provider=SceneProvider()
                ).get_job(1, queued.job_id)
                assert result.status == "processing"
        finally:
            writer.rollback()


def test_scene_failure_preserves_ready_audio_and_retry_only_synthesizes_missing(voice_db):
    with voice_db() as db:
        provider = SceneProvider()
        service = StoryVoiceReadingService(StoryVoiceReadingRepository(db), provider=provider)
        queued = service.request_reading(1, request())
        failed = service.process_job(1, queued.job_id)
        assert failed.status == "failed"
        assert [s.status for s in failed.segments] == ["ready", "failed", "queued"]
        assert failed.playback_mode == "audio"
        first_asset = failed.segments[0].asset_id
        provider.fail_scene = False
        retried = service.request_reading(1, request())
        assert retried.segments[0].asset_id == first_asset
        assert retried.segments[0].status == "ready"
        ready = service.process_job(1, queued.job_id)
        assert ready.status == "ready"
        assert provider.calls == [
            "第一段已经完成。",
            "第二段供应商暂时失败。",
            "第二段供应商暂时失败。",
            "第三段还没有执行。",
        ]


def test_assembly_failure_preserves_all_audio_and_retry_only_assembles(voice_db):
    with voice_db() as db:
        provider = SceneProvider()
        provider.fail_scene = False
        provider.fail_assembly = True
        service = StoryVoiceReadingService(StoryVoiceReadingRepository(db), provider=provider)
        queued = service.request_reading(1, request())
        failed = service.process_job(1, queued.job_id)
        assert failed.status == "failed"
        assert [s.status for s in failed.segments] == ["ready", "ready", "ready"]
        assert all(s.audio_url for s in failed.segments)
        provider.fail_assembly = False
        service.request_reading(1, request())
        assert service.process_job(1, queued.job_id).status == "ready"
        assert len(provider.calls) == 3


def test_playback_does_not_request_an_ai_plan_when_absent(voice_db, monkeypatch):
    calls = []

    class Client:
        api_key = "configured"

        def call(self, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("playback must never wait for this network call")

    monkeypatch.setattr("src.ai.client.AIClient", lambda: Client())
    monkeypatch.setenv("ENABLE_AI_NARRATION_PLAN", "1")
    monkeypatch.delenv("STORY_TTS_DISABLE_NARRATION_PLAN_AI", raising=False)
    with voice_db() as db:
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(db), provider=DeterministicTTSProvider()
        )
        queued = service.request_reading(1, request())
        result = service.process_job(1, queued.job_id)
        assert result.status == "ready"
        assert calls == []
        assert result.narration_plan_ai_attempts == 0


def test_synthesis_runs_without_an_open_database_transaction(voice_db):
    with voice_db() as db:
        provider = SceneProvider()
        provider.fail_scene = False
        transactions = []
        provider.during_scene = lambda: transactions.append(db.in_transaction())
        service = StoryVoiceReadingService(StoryVoiceReadingRepository(db), provider=provider)
        queued = service.request_reading(1, request())
        assert service.process_job(1, queued.job_id).status == "ready"
        assert transactions == [False, False, False]


def test_expiry_and_forced_retry_preserve_committed_ready_segments(voice_db):
    with voice_db() as db:
        repo = StoryVoiceReadingRepository(db)
        service = StoryVoiceReadingService(repo, provider=SceneProvider())
        queued = service.request_reading(1, request())
        service.process_job(1, queued.job_id)
        job = db.get(VoiceReadingJob, queued.job_id)
        # Seed the historical valid ready state independently of failure handling.
        job.segments[0].status = "ready"
        job.status = "processing"
        job.updated_at = datetime.utcnow() - timedelta(minutes=11)
        db.commit()
        assert repo.fail_stale_processing_job(1, queued.job_id)
        assert service.get_job(1, queued.job_id).segments[0].status == "ready"
        job = db.get(VoiceReadingJob, queued.job_id)
        job.status = "processing"
        db.commit()
        assert repo.force_requeue_processing_job(1, queued.job_id)
        assert service.get_job(1, queued.job_id).segments[0].status == "ready"


def test_plan_commit_is_rejected_after_another_worker_replaces_the_lease(voice_db):
    with voice_db() as old:
        repo = StoryVoiceReadingRepository(old)
        service = StoryVoiceReadingService(repo, provider=SceneProvider())
        queued = service.request_reading(1, request())
        old_token = repo.claim_queued_job_for_processing_with_token(1, queued.job_id)
        with voice_db() as new:
            replacement = StoryVoiceReadingRepository(new)
            replacement.force_requeue_processing_job(1, queued.job_id)
            new.commit()
            new_token = replacement.claim_queued_job_for_processing_with_token(1, queued.job_id)
        outcome = repo.commit_processing_changes(
            1, queued.job_id, old_token, context_json={"narration_plan": {"source": "stale-worker"}}
        )
        assert outcome is None
        with voice_db() as observer:
            job = observer.get(VoiceReadingJob, queued.job_id)
            assert job.updated_at == new_token
            assert job.context_json.get("narration_plan") is None


def test_worker_recovers_stale_jobs_with_a_persistent_attempt_limit(voice_db):
    from src.services.story_voice_worker import StoryVoiceWorker

    with voice_db() as db:
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(db), provider=SceneProvider()
        )
        queued = service.request_reading(1, request())
        service.process_job(1, queued.job_id)
        job = db.get(VoiceReadingJob, queued.job_id)
        job.segments[0].status = "ready"
        job.status = "processing"
        job.updated_at = datetime.utcnow() - timedelta(minutes=11)
        job.context_json = {**job.context_json, "_voice_worker_recoveries": 2}
        db.commit()
    worker = StoryVoiceWorker(session_factory=voice_db, provider_factory=SceneProvider)
    try:
        assert worker.submit(1, queued.job_id)
        worker.stop(wait=True)
        with voice_db() as db:
            job = db.get(VoiceReadingJob, queued.job_id)
            assert job.status == "failed"
            assert job.error_code == "tts_processing_timeout"
            assert job.segments[0].status == "ready"
    finally:
        worker.stop(wait=True)


def test_worker_has_no_waiting_future_queue_and_recovers_unscheduled_jobs(voice_db):
    from threading import Event, Lock
    from src.services.story_voice_worker import StoryVoiceWorker

    started = Event()
    release = Event()
    guard = Lock()
    running = []

    class BlockingProvider(DeterministicTTSProvider):
        def synthesize(self, context, voice_id, speed, on_progress=None):
            with guard:
                running.append(context["text"])
                if len(running) == 2:
                    started.set()
            assert release.wait(5)
            return super().synthesize(context, voice_id, speed, on_progress=on_progress)

    ids = []
    with voice_db() as db:
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(db), provider=BlockingProvider()
        )
        for voice in ("clear_neutral", "warm_female", "calm_male"):
            ids.append(
                service.request_reading(1, request().model_copy(update={"voice_id": voice})).job_id
            )
        db.commit()
    worker = StoryVoiceWorker(
        session_factory=voice_db, provider_factory=BlockingProvider, max_workers=2
    )
    try:
        assert worker.submit(1, ids[0])
        assert worker.submit(1, ids[1])
        assert started.wait(3)
        assert worker.submit(1, ids[2]) is False
        with voice_db() as db:
            assert db.get(VoiceReadingJob, ids[2]).status == "queued"
        release.set()
        worker.stop(wait=True)
        # A new process scans the durable queue without requiring a GET/read.
        recovered = StoryVoiceWorker(session_factory=voice_db, provider_factory=BlockingProvider)
        try:
            recovered.scan_once()
            recovered.stop(wait=True)
        finally:
            recovered.stop(wait=True)
        with voice_db() as db:
            assert [db.get(VoiceReadingJob, i).status for i in ids] == ["ready", "ready", "ready"]
    finally:
        release.set()
        worker.stop(wait=True)


@pytest.mark.parametrize(
    "changed", [{"speed": 1.8}, {"text_hash": "different-text"}, {"user_id": 99}]
)
def test_retry_rebuilds_ready_segment_when_asset_identity_does_not_match(voice_db, changed):
    with voice_db() as db:
        provider = SceneProvider()
        service = StoryVoiceReadingService(StoryVoiceReadingRepository(db), provider=provider)
        queued = service.request_reading(1, request())
        service.process_job(1, queued.job_id)
        job = db.get(VoiceReadingJob, queued.job_id)
        for field, value in changed.items():
            setattr(job.segments[0].asset, field, value)
        db.commit()
        provider.fail_scene = False
        service.request_reading(1, request())
        assert service.process_job(1, queued.job_id).status == "ready"
        assert provider.calls.count("第一段已经完成。") == 2
