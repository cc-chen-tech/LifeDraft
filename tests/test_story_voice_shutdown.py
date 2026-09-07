"""Cooperative shutdown must release executor threads and retain recoverable audio."""

import os
import subprocess
import sys
import textwrap
from threading import Event

import pytest

from src.database.models import VoiceReadingJob
from src.services.story_voice_reading import StoryVoiceReadingService
from src.services.story_voice_repository import StoryVoiceReadingRepository
from src.services.story_voice_worker import StoryVoiceWorker
from tests.test_story_voice_recovery import SceneProvider, request, voice_db as _voice_db

voice_db = _voice_db


@pytest.mark.parametrize("replace_lease", [False, True])
@pytest.mark.parametrize("stage", ["scene", "assembly"])
def test_stop_interrupts_active_progress_and_preserves_ready_audio(voice_db, replace_lease, stage):
    started, release, finished = Event(), Event(), Event()

    class WaitingSceneProvider(SceneProvider):
        fail_scene = False

        def wait_for_stop(self, on_progress):
            started.set()
            assert release.wait(3)
            try:
                on_progress()
            finally:
                finished.set()

        def synthesize_scene(self, context, voice_id, speed, on_progress=None):
            if stage == "scene" and context["text"].startswith("第二段"):
                self.wait_for_stop(on_progress)
            return super().synthesize_scene(context, voice_id, speed, on_progress)

        def assemble_scenes(self, paths, context, voice_id, speed, on_progress=None):
            if stage == "assembly":
                self.wait_for_stop(on_progress)
            return super().assemble_scenes(paths, context, voice_id, speed, on_progress)

    provider = WaitingSceneProvider()
    with voice_db() as db:
        job_id = StoryVoiceReadingService(
            StoryVoiceReadingRepository(db), provider=provider
        ).request_reading(1, request()).job_id
        db.commit()
    worker = StoryVoiceWorker(session_factory=voice_db, provider_factory=lambda: provider)
    try:
        assert worker.submit(1, job_id)
        assert started.wait(3)
        with voice_db() as db:
            ready_asset = db.get(VoiceReadingJob, job_id).segments[0].asset_id
            if replace_lease:
                repo = StoryVoiceReadingRepository(db)
                repo.force_requeue_processing_job(1, job_id)
                db.commit()
                replacement_token = repo.claim_queued_job_for_processing_with_token(1, job_id)
        worker.stop(wait=False)
        assert worker.submit(1, 999) is False
        release.set()
        assert finished.wait(1), "active callback did not observe shutdown"
        worker.stop(wait=True)
        with voice_db() as db:
            job = db.get(VoiceReadingJob, job_id)
            assert job.status == ("processing" if replace_lease else "queued")
            assert job.segments[0].status == "ready"
            assert job.segments[0].asset_id == ready_asset
            assert [s.status for s in job.segments[1:]] == (
                ["queued", "queued"] if stage == "scene" else ["ready", "ready"]
            )
            assert job.error_code is None
            if replace_lease:
                assert job.updated_at == replacement_token
        assert provider.calls == (
            ["第一段已经完成。"] if stage == "scene" else
            ["第一段已经完成。", "第二段供应商暂时失败。", "第三段还没有执行。"]
        )
        if not replace_lease:
            with voice_db() as db:
                service = StoryVoiceReadingService(StoryVoiceReadingRepository(db), provider=provider)
                assert service.process_job(1, job_id).status == "ready"
            assert provider.calls == ["第一段已经完成。", "第二段供应商暂时失败。", "第三段还没有执行。"]
    finally:
        release.set()
        worker.stop(wait=True)


def test_stop_releases_executor_on_real_interpreter_exit(tmp_path):
    # A returning stop() alone doesn't prove shutdown: CPython joins executor
    # threads at exit. The child uses a live callback loop, not a fake executor.
    script = textwrap.dedent('''
        from threading import Event
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.database.models import Base, User
        from src.services.story_tts_provider import DeterministicTTSProvider
        from src.services.story_voice_reading import StoryVoiceReadingService
        from src.services.story_voice_repository import StoryVoiceReadingRepository
        from src.services.story_voice_worker import StoryVoiceWorker
        from tests.test_story_voice_recovery import request
        started = Event()
        class WaitingProvider(DeterministicTTSProvider):
            def synthesize(self, context, voice_id, speed, on_progress=None):
                started.set()
                while True:
                    Event().wait(0.02)
                    on_progress()
        engine = create_engine(__import__('os').environ['DATABASE_URL'])
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine)
        with sessions() as db:
            db.add(User(user_id=1, private_id='shutdown', public_id='shutdown', display_name='Test'))
            db.commit()
            job_id = StoryVoiceReadingService(StoryVoiceReadingRepository(db), provider=WaitingProvider()).request_reading(1, request()).job_id
            db.commit()
        worker = StoryVoiceWorker(session_factory=sessions, provider_factory=WaitingProvider)
        assert worker.submit(1, job_id)
        assert started.wait(3)
        worker.stop(wait=False)
        print('STOP_RETURNED', flush=True)
    ''')
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'child.db'}"}
    child = subprocess.Popen([sys.executable, "-c", script], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = child.communicate(timeout=6)
    except subprocess.TimeoutExpired:
        child.kill()
        stdout, stderr = child.communicate()
        pytest.fail(f"stop returned but interpreter still joins active synthesis: {stdout}\n{stderr}")
    assert child.returncode == 0, stderr
    assert "STOP_RETURNED" in stdout
