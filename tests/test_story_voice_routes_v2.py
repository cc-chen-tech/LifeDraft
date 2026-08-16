from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from src.api.deps import get_current_user
from src.api.main import app
from src.database.models import SessionLocal, User, init_db
from src.services.story_voice_reading import normalize_text_hash


def _create_user() -> int:
    init_db()
    session = SessionLocal()
    try:
        user = User(
            private_id=f"route-{uuid4().hex[:20]}",
            public_id=f"R{uuid4().hex[:7]}",
            display_name="Route listener",
        )
        session.add(user)
        session.commit()
        return int(user.user_id)
    finally:
        session.close()


def test_read_route_queues_background_paragraph_generation(monkeypatch) -> None:
    monkeypatch.setenv("MINIMAX_E2E_LOCAL_AUDIO", "true")
    user_id = _create_user()
    text = "路由第一段。\n\n路由第二段。"
    app.dependency_overrides[get_current_user] = lambda: user_id
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/voice-reading/read",
                json={
                    "context": {
                        "source_type": "current_story",
                        "game_id": 990,
                        "week": 1,
                        "round_number": 1,
                        "stage": "event",
                        "day_index": 0,
                        "story_date": "2026-08-15",
                        "text_hash": normalize_text_hash(text),
                        "text": text,
                    },
                    "voice_id": "warm_female",
                    "speed": 1.0,
                },
            )

            assert response.status_code == 200
            queued = response.json()
            assert queued["status"] == "queued"
            assert len(queued["segments"]) == 2

            recovered = client.get(f"/api/voice-reading/jobs/{queued['job_id']}")
            assert recovered.status_code == 200
            assert recovered.json()["status"] == "ready"
            assert all(segment["audio_url"] for segment in recovered.json()["segments"])
    finally:
        app.dependency_overrides.clear()


def test_progress_routes_round_trip_only_for_current_user(monkeypatch) -> None:
    monkeypatch.setenv("MINIMAX_E2E_LOCAL_AUDIO", "true")
    user_id = _create_user()
    app.dependency_overrides[get_current_user] = lambda: user_id
    payload = {
        "game_id": 990,
        "day_index": 4,
        "story_date": "2026-08-15",
        "text_hash": "route-progress-hash",
        "voice_id": "calm_male",
        "speed": 1.25,
        "paragraph_index": 3,
        "position_ms": 2180,
        "completed": False,
    }
    try:
        with TestClient(app) as client:
            saved = client.patch("/api/voice-reading/progress", json=payload)
            loaded = client.get(
                "/api/voice-reading/progress",
                params={key: payload[key] for key in (
                    "game_id", "day_index", "text_hash", "voice_id", "speed"
                )},
            )

            assert saved.status_code == 200
            assert loaded.status_code == 200
            assert loaded.json()["paragraph_index"] == 3
            assert loaded.json()["position_ms"] == 2180
    finally:
        app.dependency_overrides.clear()


def test_health_exposes_daily_tts_and_music_runtime_capabilities(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_DAILY_TIMELINE_V2", "true")
    monkeypatch.setenv("MINIMAX_E2E_LOCAL_AUDIO", "true")

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["capabilities"] == {
        "daily_timeline_v2": True,
        "daily_recommended_prefetch": False,
        "daily_recommended_tts_prefetch": False,
        "tts_provider": "minimax",
        "tts_provider_available": True,
        "tts_audio_transport": "range_v2",
        "music_runtime_enabled": False,
    }


def test_music_runtime_routes_are_not_registered() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    assert not any(path == "/api/music" or path.startswith("/api/music/") for path in paths)
