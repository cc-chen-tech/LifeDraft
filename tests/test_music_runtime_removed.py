from pathlib import Path

from src.api.main import app
import pytest

pytestmark = [pytest.mark.unit]



ROOT = Path(__file__).resolve().parents[1]


def test_music_routes_are_absent_from_runtime_and_openapi() -> None:
    route_paths = {getattr(route, "path", "") for route in app.routes}
    schema = (ROOT / "frontend/src/types/openapi-schema.json").read_text(encoding="utf-8")

    assert not any(path == "/api/music" or path.startswith("/api/music/") for path in route_paths)
    assert '"/api/music' not in schema


def test_production_frontend_has_no_music_or_unified_sound_entry() -> None:
    production_files = [
        ROOT / "frontend/src/app/layout.tsx",
        ROOT / "frontend/src/app/play/page.tsx",
        ROOT / "frontend/src/components/game/PlayTools.tsx",
    ]

    for path in production_files:
        source = path.read_text(encoding="utf-8")
        assert "GlobalMusicPlayer" not in source
        assert "useMusicStore" not in source
        assert "打开声音" not in source


def test_ecs_deployment_has_no_netease_music_runtime_references() -> None:
    compose = (ROOT / "docker-compose.ecs.yml").read_text(encoding="utf-8")
    nginx_configs = [
        ROOT / "nginx/ecs-nginx.conf",
        ROOT / "nginx/ecs-nginx-http.conf",
    ]

    assert "music-api:" not in compose
    assert "story2-music" not in compose
    assert "netease-music-api" not in compose
    for path in nginx_configs:
        source = path.read_text(encoding="utf-8")
        assert "music-api" not in source
        assert "/api/music/" not in source
        assert "location /music/" not in source
