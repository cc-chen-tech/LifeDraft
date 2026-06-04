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
        "tts_provider",
        "tts_model",
        "tts_provider_available",
        "backend_audio_enabled",
        "playback_mode",
    } <= _fields(VoiceReadingSettingsResponse)
    assert {"selected_voice_color", "auto_read_enabled"} <= _fields(
        VoiceReadingSettingsUpdateRequest
    )
    assert "voice_reading" in FRONTEND_API
    assert "getSettings" in FRONTEND_API
    assert "updateSettings" in FRONTEND_API
    assert "requestReading" in FRONTEND_API


def test_story_voice_controls_use_browser_speech_for_immediate_text_reading() -> None:
    component = (
        ROOT / "frontend" / "src" / "components" / "game" / "StoryVoiceControls.tsx"
    ).read_text(encoding="utf-8")
    store = (
        ROOT / "frontend" / "src" / "stores" / "useStoryVoiceStore.ts"
    ).read_text(encoding="utf-8")

    assert "voice-reading-job" in component
    assert "voice-reading-audio-url" in component
    assert "api.voice_reading.requestReading" in store
    assert "crypto.subtle.digest" in store
    assert "playback_mode === \"audio\"" in store
    assert "speechSynthesis" in store
    assert "SpeechSynthesisUtterance" in store
    assert "voice-reading-mode" in component
    assert "voice-reading-spoken-length" in component
    assert "voice-reading-playback-mode" in component
    assert "voice-reading-speech-text" in component


def test_story_voice_reading_routes_are_registered_before_browser_e2e() -> None:
    routes = {getattr(route, "path", "") for route in app.routes}

    assert "/api/voice-reading/settings" in routes
    assert "/api/voice-reading/read" in routes
    assert "/api/voice-reading/jobs/{job_id}" in routes
    assert "/api/voice-reading/upload-consent" in routes
    assert "/api/voice-reading/audio/{file_name}" in routes


def test_story_voice_response_does_not_force_wav_for_browser_fallback() -> None:
    fields = _fields(StoryVoiceReadingResponse)
    store = (
        ROOT / "frontend" / "src" / "stores" / "useStoryVoiceStore.ts"
    ).read_text(encoding="utf-8")

    assert {"playback_mode", "provider", "model", "media_type"} <= fields
    assert "browser_speech" in FRONTEND_TYPES
    assert "currentSpeechText" in store


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
