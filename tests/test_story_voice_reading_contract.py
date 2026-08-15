"""Producer/consumer contracts for story voice reading."""

from pathlib import Path

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.schemas import (
    ReadingContext,
    StoryVoiceErrorResponse,
    StoryVoiceReadingRequest,
    StoryVoiceReadingResponse,
    VoiceAssetResponse,
    VoiceReadingJobResponse,
    VoiceReadingSettingsResponse,
    VoiceReadingSettingsUpdateRequest,
)

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_TYPES = (ROOT / "frontend" / "src" / "lib" / "types.ts").read_text(encoding="utf-8")
FRONTEND_API = (ROOT / "frontend" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")


def _fields(model: type) -> set[str]:
    return set(model.model_fields.keys())


def test_reading_context_fields_match_frontend_contract() -> None:
    required = {
        "source_type",
        "game_id",
        "week",
        "round_number",
        "stage",
        "attempt_id",
        "text_hash",
        "text",
    }

    assert required <= _fields(ReadingContext)
    assert "export interface ReadingContext" in FRONTEND_TYPES
    for field in required:
        assert f"{field}:" in FRONTEND_TYPES or f"{field}?:" in FRONTEND_TYPES


def test_story_voice_response_fields_match_frontend_contract() -> None:
    response_fields = {
        "job_id",
        "status",
        "audio_url",
        "asset_id",
        "duration_ms",
        "playback_mode",
        "provider",
        "model",
        "media_type",
        "error_code",
        "message",
    }
    asset_fields = {
        "asset_id",
        "source_type",
        "text_hash",
        "voice_id",
        "provider",
        "model",
        "storage_path",
        "duration_ms",
        "status",
    }

    assert {"context", "voice_id", "speed", "auto_play"} <= _fields(StoryVoiceReadingRequest)
    assert response_fields <= _fields(StoryVoiceReadingResponse)
    assert response_fields <= _fields(VoiceReadingJobResponse)
    assert asset_fields <= _fields(VoiceAssetResponse)
    assert {"error_code", "message", "field"} <= _fields(StoryVoiceErrorResponse)

    for interface_name in (
        "StoryVoiceReadingRequest",
        "StoryVoiceReadingResponse",
        "VoiceReadingJobResponse",
        "VoiceAssetResponse",
        "StoryVoiceErrorResponse",
    ):
        assert f"export interface {interface_name}" in FRONTEND_TYPES

    for field in response_fields | asset_fields | {"error_code", "message", "field"}:
        assert f"{field}:" in FRONTEND_TYPES or f"{field}?:" in FRONTEND_TYPES


def test_voice_settings_contract_supports_reading_defaults() -> None:
    assert {
        "member_required",
        "enabled",
        "available_voice_colors",
        "selected_voice_color",
        "uploaded_voice_available",
        "auto_read_enabled",
        "selected_speed",
        "tts_provider",
        "tts_model",
        "tts_provider_available",
        "backend_audio_enabled",
        "playback_mode",
    } <= _fields(VoiceReadingSettingsResponse)
    assert {"selected_voice_color", "auto_read_enabled", "selected_speed"} <= _fields(
        VoiceReadingSettingsUpdateRequest
    )
    assert "voice_reading" in FRONTEND_API
    assert "getSettings" in FRONTEND_API
    assert "updateSettings" in FRONTEND_API
    assert "requestReading" in FRONTEND_API


def test_daily_listener_uses_chapter_audio_without_browser_speech() -> None:
    component = (
        ROOT / "frontend" / "src" / "components" / "game" / "StoryListeningExperience.tsx"
    ).read_text(encoding="utf-8")
    hash_helper = (
        ROOT / "frontend" / "src" / "lib" / "storyVoiceTextHash.ts"
    ).read_text(encoding="utf-8")

    assert "api.voice_reading.requestReading" in component
    assert "api.voice_reading.getProgress" in component
    assert "api.voice_reading.updateProgress" in component
    assert "storyVoiceTextToHash" in component
    assert "crypto.subtle.digest" in hash_helper
    assert "speechSynthesis" not in component
    assert "SpeechSynthesisUtterance" not in component
    assert "从第 ${index + 1} 段开始朗读" in component


def test_story_voice_reading_routes_are_registered_before_browser_e2e() -> None:
    routes = {getattr(route, "path", "") for route in app.routes}

    assert "/api/voice-reading/settings" in routes
    assert "/api/voice-reading/read" in routes
    assert "/api/voice-reading/jobs/{job_id}" in routes
    assert "/api/voice-reading/progress" in routes
    assert "/api/voice-reading/upload-consent" in routes
    assert "/api/voice-reading/audio/{file_name}" in routes


def test_story_voice_response_exposes_only_backend_audio_or_unavailable() -> None:
    fields = _fields(StoryVoiceReadingResponse)

    assert {"playback_mode", "provider", "model", "media_type"} <= fields
    assert "browser_speech" not in FRONTEND_TYPES
    assert 'playback_mode: "audio" | "unavailable"' in FRONTEND_TYPES


def test_voice_reading_audio_route_serves_minimax_mp3_assets(tmp_path: Path) -> None:
    import os

    asset_dir = tmp_path / "voice-assets"
    asset_dir.mkdir()
    mp3_file = asset_dir / "minimax-story.mp3"
    mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")
    previous_asset_dir = os.environ.get("STORY_TTS_ASSET_DIR")
    os.environ["STORY_TTS_ASSET_DIR"] = str(asset_dir)
    try:
        response = TestClient(app).get("/api/voice-reading/audio/minimax-story.mp3")
    finally:
        if previous_asset_dir is None:
            os.environ.pop("STORY_TTS_ASSET_DIR", None)
        else:
            os.environ["STORY_TTS_ASSET_DIR"] = previous_asset_dir

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/mpeg")
    assert response.content.startswith(b"ID3")


def test_voice_reading_audio_route_never_synthesizes_local_fixture_in_runtime(
    monkeypatch,
) -> None:
    monkeypatch.delenv("MINIMAX_E2E_LOCAL_AUDIO", raising=False)

    response = TestClient(app).get(
        "/api/voice-reading/audio/guessed-hash-warm_female.wav"
    )

    assert response.status_code == 404
