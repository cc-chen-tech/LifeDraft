"""HTTP trace IDs bridge to durable narration jobs only after commit."""

import logging
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event

from src.api.deps import create_token, get_session
from src.api.main import AuditLogMiddleware
from src.api.routers.voice_reading import router
from src.database.models import VoiceReadingJob
from src.services.story_tts_provider import DeterministicTTSProvider
from src.services.story_voice_worker import StoryVoiceWorker
from tests.test_story_voice_recovery import request, voice_db as _voice_db

voice_db = _voice_db


def voice_app(voice_db, monkeypatch, *, fail_commit=False):
    monkeypatch.setenv("JWT_SECRET", "enqueue-trace-test-secret")
    monkeypatch.setattr(
        "src.services.story_voice_reading.build_story_tts_provider",
        DeterministicTTSProvider,
    )
    # Simulate no immediate worker capacity; committed work must survive restart.
    monkeypatch.setattr(
        "src.api.routers.voice_reading.submit_story_voice_job", lambda *_: False
    )
    app = FastAPI()
    app.add_middleware(AuditLogMiddleware)
    app.include_router(router, prefix="/api/voice-reading")

    def session():
        with voice_db() as db:
            if fail_commit:

                def reject_commit(_session):
                    raise RuntimeError("private database statement sk-secret")

                event.listen(db, "before_commit", reject_commit)
            yield db

    app.dependency_overrides[get_session] = session
    return app


def event_payloads(caplog, name):
    return [
        record.event_data
        for record in caplog.records
        if getattr(record, "event", None) == name
    ]


def test_committed_route_trace_joins_restarted_worker_by_job(
    voice_db, monkeypatch, caplog
):
    caplog.set_level(logging.INFO, logger="diagnostic")
    app = voice_app(voice_db, monkeypatch)
    client = TestClient(app)
    client.cookies.set("auth_token", create_token(1))
    response = client.post(
        "/api/voice-reading/read",
        json=request().model_dump(),
        headers={
            "X-Request-ID": "voice-http-request",
            "X-Operation-ID": "voice-http-operation",
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    with voice_db() as db:
        assert db.get(VoiceReadingJob, job_id).status == "queued"
    enqueue = event_payloads(caplog, "voice_job_enqueued")
    assert len(enqueue) == 1
    assert (
        enqueue[0].items()
        >= {
            "user_id": 1,
            "game_id": 77,
            "job_id": job_id,
            "job_type": "voice",
            "request_id": "voice-http-request",
            "operation_id": "voice-http-operation",
            "status": "queued",
            "persisted": True,
            "outcome": "success",
        }.items()
    )
    worker = StoryVoiceWorker(
        session_factory=voice_db, provider_factory=DeterministicTTSProvider
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
            pytest.fail("restarted worker did not process committed job")
    finally:
        worker.stop(wait=True)
    delivery = [
        p for p in event_payloads(caplog, "voice_job") if p["phase"] == "delivery"
    ]
    assert delivery[0]["job_id"] == enqueue[0]["job_id"]
    assert delivery[0]["user_id"] == enqueue[0]["user_id"]
    assert delivery[0]["operation_id"] == f"voice:{job_id}"


def test_failed_enqueue_commit_records_failure_without_success_or_durable_job(
    voice_db, monkeypatch, caplog
):
    caplog.set_level(logging.INFO, logger="diagnostic")
    app = voice_app(voice_db, monkeypatch, fail_commit=True)
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("auth_token", create_token(1))
    response = client.post(
        "/api/voice-reading/read",
        json=request().model_dump(),
        headers={
            "X-Request-ID": "failed-http-request",
            "X-Operation-ID": "failed-http-operation",
        },
    )
    assert response.status_code == 500
    with voice_db() as db:
        assert db.query(VoiceReadingJob).count() == 0
    assert event_payloads(caplog, "voice_job_enqueued") == []
    failed = event_payloads(caplog, "voice_job_enqueue_failed")
    assert len(failed) == 1
    assert (
        failed[0].items()
        >= {
            "user_id": 1,
            "game_id": 77,
            "persisted": False,
            "request_id": "failed-http-request",
            "operation_id": "failed-http-operation",
            "phase": "enqueue",
            "outcome": "failure",
            "exception_type": "RuntimeError",
        }.items()
    )
    assert "private database" not in str(failed)
    assert "sk-secret" not in str(failed)
