"""HTTP transport contracts for provider-generated narration assets."""

from pathlib import Path

from fastapi.testclient import TestClient

from src.api.main import app
import pytest

pytestmark = [pytest.mark.unit]



def _write_minimax_asset(asset_dir: Path) -> None:
    (asset_dir / "minimax-range.mp3").write_bytes(b"0123456789")


def test_voice_reading_audio_returns_a_range_capable_file_response(
    tmp_path: Path, monkeypatch
) -> None:
    """Replacing FileResponse with a byte buffer must break audio transport headers."""
    _write_minimax_asset(tmp_path)
    monkeypatch.setenv("STORY_TTS_ASSET_DIR", str(tmp_path))

    response = TestClient(app).get("/api/voice-reading/audio/minimax-range.mp3")

    assert response.status_code == 200
    assert response.content == b"0123456789"
    assert response.headers["content-type"].startswith("audio/mpeg")
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == "10"
    assert response.headers["last-modified"]
    assert response.headers["etag"]


def test_voice_reading_audio_supports_prefix_range(tmp_path: Path, monkeypatch) -> None:
    """Removing path-based transport must break an explicit byte prefix request."""
    _write_minimax_asset(tmp_path)
    monkeypatch.setenv("STORY_TTS_ASSET_DIR", str(tmp_path))

    response = TestClient(app).get(
        "/api/voice-reading/audio/minimax-range.mp3", headers={"Range": "bytes=2-5"}
    )

    assert response.status_code == 206
    assert response.content == b"2345"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == "4"
    assert response.headers["content-range"] == "bytes 2-5/10"


def test_voice_reading_audio_supports_suffix_range(tmp_path: Path, monkeypatch) -> None:
    """Removing range support must break trailing-byte audio resumes."""
    _write_minimax_asset(tmp_path)
    monkeypatch.setenv("STORY_TTS_ASSET_DIR", str(tmp_path))

    response = TestClient(app).get(
        "/api/voice-reading/audio/minimax-range.mp3", headers={"Range": "bytes=-3"}
    )

    assert response.status_code == 206
    assert response.content == b"789"
    assert response.headers["content-range"] == "bytes 7-9/10"


def test_voice_reading_audio_supports_open_ended_range(tmp_path: Path, monkeypatch) -> None:
    """Removing range support must break an open-ended audio resume."""
    _write_minimax_asset(tmp_path)
    monkeypatch.setenv("STORY_TTS_ASSET_DIR", str(tmp_path))

    response = TestClient(app).get(
        "/api/voice-reading/audio/minimax-range.mp3", headers={"Range": "bytes=7-"}
    )

    assert response.status_code == 206
    assert response.content == b"789"
    assert response.headers["content-range"] == "bytes 7-9/10"


def test_voice_reading_audio_rejects_unsatisfiable_range(tmp_path: Path, monkeypatch) -> None:
    """Dropping the bytes unit from an unsatisfied Content-Range must fail."""
    _write_minimax_asset(tmp_path)
    monkeypatch.setenv("STORY_TTS_ASSET_DIR", str(tmp_path))

    response = TestClient(app).get(
        "/api/voice-reading/audio/minimax-range.mp3", headers={"Range": "bytes=20-30"}
    )

    assert response.status_code == 416
    assert response.headers["content-range"] == "bytes */10"


def test_voice_reading_audio_honors_if_range(tmp_path: Path, monkeypatch) -> None:
    """A stale validator must fall back to the complete MiniMax asset."""
    _write_minimax_asset(tmp_path)
    monkeypatch.setenv("STORY_TTS_ASSET_DIR", str(tmp_path))
    client = TestClient(app)
    url = "/api/voice-reading/audio/minimax-range.mp3"
    validator = client.get(url).headers["etag"]

    matching = client.get(url, headers={"Range": "bytes=0-1", "If-Range": validator})
    stale = client.get(url, headers={"Range": "bytes=0-1", "If-Range": '"stale"'})

    assert matching.status_code == 206
    assert matching.content == b"01"
    assert stale.status_code == 200
    assert stale.content == b"0123456789"


def test_voice_reading_audio_rejects_path_escape(tmp_path: Path, monkeypatch) -> None:
    """Changing safe asset resolution must not expose files outside the asset directory."""
    _write_minimax_asset(tmp_path)
    monkeypatch.setenv("STORY_TTS_ASSET_DIR", str(tmp_path))

    response = TestClient(app).get("/api/voice-reading/audio/..%2Fsecret.mp3")

    assert response.status_code == 404
