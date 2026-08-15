"""Deployment contracts for range-capable narration audio transport."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAMES = ("ecs-nginx.conf", "ecs-nginx-http.conf")


def _audio_location(source: str) -> str:
    match = re.search(
        r"location /api/voice-reading/audio/ \{(?P<block>.*?)^        \}",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "voice-reading audio must have its own Nginx location"
    return match.group("block")


def test_ecs_nginx_isolates_voice_audio_from_sse_transport() -> None:
    """An audio location must retain Range validators without SSE websocket behavior."""
    for name in NAMES:
        block = _audio_location((ROOT / "nginx" / name).read_text(encoding="utf-8"))

        assert "proxy_pass http://backend/api/voice-reading/audio/;" in block
        assert "proxy_set_header Range $http_range;" in block
        assert "proxy_set_header If-Range $http_if_range;" in block
        assert 'proxy_set_header Upgrade "";' in block
        assert 'proxy_set_header Connection "";' in block
        assert "proxy_buffering on;" in block
        assert "proxy_buffering off" not in block
