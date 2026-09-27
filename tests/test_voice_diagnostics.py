"""Voice failures remain attributable across workers and recovery."""

import logging
import time

import pytest
from src.database.models import User, VoiceReadingJob
from src.services.story_voice_reading import StoryVoiceReadingService
from src.services.story_voice_repository import StoryVoiceReadingRepository
from src.services.story_voice_worker import StoryVoiceWorker
from src.services.minimax_story_tts_provider import _raise_for_base_resp
from tests.test_story_voice_recovery import (
    SceneProvider,
    request,
    voice_db as _voice_db,
)

voice_db = _voice_db


def events(caplog):
    return [
        getattr(record, "event_data", {})
        for record in caplog.records
        if getattr(record, "event_data", {}).get("event", "").startswith("voice_")
    ]


def test_minimax_business_error_retains_safe_code_without_message_parsing():
    with pytest.raises(RuntimeError) as caught:
        _raise_for_base_resp(
            {
                "base_resp": {
                    "status_code": 2056,
                    "status_msg": "private story sk-secret",
                }
            }
        )
    assert getattr(caught.value, "provider_code", None) == "2056"
    assert "private story" not in str(caught.value)


def test_assembly_failure_has_attributed_terminal_event_even_after_retry(
    voice_db, caplog
):
    caplog.set_level(logging.INFO)
    provider = SceneProvider()
    provider.fail_scene = False
    provider.fail_assembly = True
    with voice_db() as db:
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(db), provider=provider
        )
        job_id = service.request_reading(1, request()).job_id
        failed = service.process_job(1, job_id)
        assert failed.status == "failed"
        assert failed.error_code == "tts_assembly_failed"
        provider.fail_assembly = False
        service.request_reading(1, request())
        assert service.process_job(1, job_id).status == "ready"
    terminal = [
        e
        for e in events(caplog)
        if e.get("outcome") == "failure" and e.get("phase") == "assembly"
    ]
    assert terminal and terminal[0]["job_id"] == job_id
    assert terminal[0]["user_id"] == 1
    assert terminal[0]["game_id"] == 77


def test_two_user_workers_rebuild_identity_without_cross_task_leaks(voice_db, caplog):
    caplog.set_level(logging.INFO)
    jobs = []
    with voice_db() as db:
        db.add(User(user_id=2, private_id="second", public_id="second"))
        db.commit()
        for user_id in (1, 2):
            service = StoryVoiceReadingService(
                StoryVoiceReadingRepository(db), provider=SceneProvider()
            )
            jobs.append((user_id, service.request_reading(user_id, request()).job_id))
        db.commit()
    worker = StoryVoiceWorker(session_factory=voice_db, provider_factory=SceneProvider)
    try:
        for pair in jobs:
            assert worker.submit(*pair)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with voice_db() as db:
                if all(
                    db.get(VoiceReadingJob, job).status == "failed" for _, job in jobs
                ):
                    break
            time.sleep(0.01)
        else:
            pytest.fail("workers did not finish")
    finally:
        worker.stop(wait=True)
    for user_id, job_id in jobs:
        matches = [e for e in events(caplog) if e.get("job_id") == job_id]
        assert matches
        assert {e["user_id"] for e in matches} == {user_id}
        assert {e["operation_id"] for e in matches} == {f"voice:{job_id}"}
        assert all(e.get("attempt_id") for e in matches)


def test_asset_insert_failure_is_persistence_failure_not_provider_failure(
    voice_db, monkeypatch, caplog
):
    caplog.set_level(logging.INFO)
    provider = SceneProvider()
    provider.fail_scene = False
    with voice_db() as db:
        repository = StoryVoiceReadingRepository(db)
        service = StoryVoiceReadingService(repository, provider=provider)
        job_id = service.request_reading(1, request()).job_id

        def fail_insert(**kwargs):
            raise RuntimeError("private story cannot be written sk-secret")

        monkeypatch.setattr(repository, "create_asset", fail_insert)
        result = service.process_job(1, job_id)
        assert result.error_code == "tts_persistence_failed"
    assert any(
        e.get("phase") == "persistence" and e.get("outcome") == "failure"
        for e in events(caplog)
    )
    assert "private story" not in str(events(caplog))


def test_failure_persistence_error_is_logged_without_replacing_original_event(
    voice_db, monkeypatch, caplog
):
    caplog.set_level(logging.INFO)
    with voice_db() as db:
        repository = StoryVoiceReadingRepository(db)
        service = StoryVoiceReadingService(repository, provider=SceneProvider())
        job_id = service.request_reading(1, request()).job_id

        def fail_commit(*args, **kwargs):
            raise RuntimeError("private SQL and secret")

        monkeypatch.setattr(repository, "commit_processing_changes", fail_commit)
        with pytest.raises(RuntimeError):
            service.process_job(1, job_id)
    failures = [e for e in events(caplog) if e.get("outcome") == "failure"]
    assert {e["phase"] for e in failures} == {"persistence", "failure_persistence"}
    assert all(e["job_id"] == job_id and e["user_id"] == 1 for e in failures)
    assert "private SQL" not in str(failures)


def test_restarted_worker_retry_retains_prior_failure_and_stable_operation(
    voice_db, caplog
):
    caplog.set_level(logging.INFO)
    with voice_db() as db:
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(db), provider=SceneProvider()
        )
        job_id = service.request_reading(1, request()).job_id
        assert service.process_job(1, job_id).status == "failed"
        service.request_reading(1, request())
        db.commit()
    provider = SceneProvider()
    provider.fail_scene = False
    worker = StoryVoiceWorker(
        session_factory=voice_db, provider_factory=lambda: provider
    )
    try:
        worker.scan_once()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with voice_db() as db:
                if db.get(VoiceReadingJob, job_id).status == "ready":
                    break
            time.sleep(0.01)
        else:
            pytest.fail("restart did not recover queued job")
    finally:
        worker.stop(wait=True)
    terminal = [
        e
        for e in events(caplog)
        if e["event"] == "voice_job" and e["outcome"] in {"failure", "success"}
    ]
    assert {e["outcome"] for e in terminal} == {"failure", "success"}
    assert {e["operation_id"] for e in terminal} == {f"voice:{job_id}"}
    assert len({e["attempt_id"] for e in terminal}) == 2
    assert all(e["user_id"] == 1 and e["game_id"] == 77 for e in terminal)
