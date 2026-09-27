"""Audio URLs authenticate cookies and authorize the stored asset owner."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.deps import create_token, get_session
from src.api.routers.voice_reading import router
from src.database.models import User
from src.services.story_voice_repository import StoryVoiceReadingRepository
from tests.test_story_voice_recovery import voice_db as _voice_db

voice_db = _voice_db


def test_audio_owner_cookie_range_and_other_user_denial(
    voice_db, tmp_path, monkeypatch
):
    monkeypatch.setenv("JWT_SECRET", "voice-test-secret-only")
    monkeypatch.setenv("STORY_TTS_ASSET_DIR", str(tmp_path))
    (tmp_path / "owned.mp3").write_bytes(b"0123456789")
    with voice_db() as db:
        db.add(User(user_id=2, private_id="other", public_id="other"))
        StoryVoiceReadingRepository(db).create_asset(
            user_id=1,
            context={"source_type": "current_story", "text_hash": "owned"},
            voice_id="warm_female",
            speed=1.0,
            provider="minimax",
            model="test",
            storage_path="/api/voice-reading/audio/owned.mp3",
            duration_ms=1000,
            status="ready",
        )
        db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api/voice-reading")

    def session():
        with voice_db() as db:
            yield db

    app.dependency_overrides[get_session] = session
    client = TestClient(app)
    url = "/api/voice-reading/audio/owned.mp3"
    assert client.get(url).status_code == 401
    client.cookies.set("auth_token", create_token(2))
    assert client.get(url).status_code == 404
    client.cookies.set("auth_token", create_token(1))
    response = client.get(url, headers={"Range": "bytes=2-5"})
    assert response.status_code == 206
    assert response.content == b"2345"
    assert response.headers["cache-control"] == "private, no-store"


def test_preview_registers_owned_asset_and_cookie_can_play_it(voice_db, monkeypatch):
    from src.services.story_tts_provider import DeterministicTTSProvider

    monkeypatch.setenv("JWT_SECRET", "voice-test-secret-only")
    monkeypatch.setenv("MINIMAX_E2E_LOCAL_AUDIO", "true")
    monkeypatch.setattr(
        "src.services.story_voice_reading.build_story_tts_provider",
        DeterministicTTSProvider,
    )
    app = FastAPI()
    app.include_router(router, prefix="/api/voice-reading")

    def session():
        with voice_db() as db:
            yield db

    app.dependency_overrides[get_session] = session
    with TestClient(app) as client:
        client.cookies.set("auth_token", create_token(1))
        preview = client.post(
            "/api/voice-reading/preview", json={"voice_id": "female-shaonv"}
        )
        assert preview.status_code == 200
        audio = client.get(preview.json()["audio_url"])
        assert audio.status_code == 200
        assert audio.content.startswith(b"RIFF")
        client.cookies.set("auth_token", create_token(2))
        assert client.get(preview.json()["audio_url"]).status_code == 404
