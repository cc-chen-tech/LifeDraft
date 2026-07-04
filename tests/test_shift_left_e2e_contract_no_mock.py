"""Shift-left contract tests for failures that should not wait for Playwright."""

from pathlib import Path

from fastapi import FastAPI
from src.api.routers import (
    auth,
    character,
    collection,
    friends,
    gameplay,
    games,
    images,
    music,
    presets,
    story,
    voice_reading,
)


ROOT = Path(__file__).resolve().parents[1]


def _build_route_contract_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
    app.include_router(friends.router, prefix="/api/friends", tags=["Friends"])
    app.include_router(games.router, prefix="/api/games", tags=["Games"])
    app.include_router(character.router, prefix="/api/character", tags=["Character"])
    app.include_router(presets.router, prefix="/api/presets", tags=["Presets"])
    app.include_router(gameplay.router, prefix="/api/games", tags=["Gameplay"])
    app.include_router(story.router, prefix="/api/games", tags=["Story"])
    app.include_router(images.router, prefix="/api/images", tags=["Images"])
    app.include_router(collection.router, prefix="/api/collection", tags=["Collection"])
    app.include_router(music.router, prefix="/api", tags=["Music"])
    app.include_router(voice_reading.router, prefix="/api/voice-reading", tags=["VoiceReading"])
    return app


def _registered_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route in _build_route_contract_app().routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if not path.startswith("/api/"):
            continue
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            routes.add((method, path))
    return routes


REQUIRED_BROWSER_API_ROUTES = {
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/me"),
    ("GET", "/api/games"),
    ("POST", "/api/games"),
    ("GET", "/api/games/active"),
    ("GET", "/api/games/{game_id}"),
    ("DELETE", "/api/games/{game_id}"),
    ("POST", "/api/games/{game_id}/save"),
    ("POST", "/api/games/{game_id}/clear-cache"),
    ("POST", "/api/games/{game_id}/choice"),
    ("POST", "/api/games/{game_id}/custom-choice"),
    ("POST", "/api/games/{game_id}/choice-sync"),
    ("POST", "/api/games/{game_id}/custom-choice-sync"),
    ("GET", "/api/games/{game_id}/event"),
    ("POST", "/api/games/{game_id}/event-sync"),
    ("GET", "/api/games/{game_id}/state"),
    ("GET", "/api/games/{game_id}/ending"),
    ("POST", "/api/games/{game_id}/summary"),
    ("GET", "/api/games/{game_id}/regenerate-stream"),
    ("POST", "/api/games/{game_id}/rewrite-stream"),
    ("POST", "/api/games/{game_id}/chat"),
    ("POST", "/api/games/{game_id}/rewrite"),
    ("POST", "/api/games/{game_id}/regenerate"),
    ("DELETE", "/api/games/{game_id}/session-debug"),
    ("POST", "/api/games/{game_id}/save-point"),
    ("GET", "/api/games/{game_id}/save-points"),
    ("GET", "/api/games/{game_id}/timeline"),
    ("GET", "/api/games/load-save-point/{state_id}"),
    ("DELETE", "/api/games/save-point/{state_id}"),
    ("GET", "/api/images/game/{game_id}"),
    ("POST", "/api/images/generate"),
    ("POST", "/api/images/regenerate"),
    ("POST", "/api/images/regenerate-fresh"),
    ("GET", "/api/images/scene/{game_id}/{round_number}"),
    ("GET", "/api/images/scenes/{game_id}"),
    ("POST", "/api/images/scene/generate"),
    ("POST", "/api/images/scene/regenerate"),
    ("POST", "/api/images/batch-characters"),
    ("POST", "/api/images/opening-illustration"),
    ("POST", "/api/images/opening-illustration/regenerate"),
    ("GET", "/api/images/{image_id}"),
    ("DELETE", "/api/images/{image_id}"),
    ("GET", "/api/collection/{game_id}"),
    ("GET", "/api/collection/{game_id}/details"),
    ("POST", "/api/collection/{game_id}/characters/{name}/generate-image"),
    ("POST", "/api/collection/{game_id}/characters/{name}/generate-description"),
    ("POST", "/api/collection/{game_id}/characters/{name}/regenerate-image"),
    ("POST", "/api/collection/{game_id}/items/{item_name}/generate-image"),
    ("POST", "/api/collection/{game_id}/items/{item_name}/regenerate-image"),
    ("POST", "/api/collection/{game_id}/items/{item_name}/generate-description"),
    ("POST", "/api/collection/{game_id}/landmarks/{landmark_name}/generate-image"),
    ("POST", "/api/collection/{game_id}/landmarks/{landmark_name}/generate-description"),
    ("POST", "/api/collection/{game_id}/recognize-entities"),
    ("POST", "/api/collection/{game_id}/add-entities"),
    ("POST", "/api/collection/{game_id}/items/create"),
    ("DELETE", "/api/collection/{game_id}/items/{item_name}"),
    ("DELETE", "/api/collection/{game_id}/characters/{character_name}"),
    ("DELETE", "/api/collection/{game_id}/landmarks/{landmark_name}"),
    ("POST", "/api/character/opening-story"),
    ("POST", "/api/character/setting"),
    ("POST", "/api/character/relationship"),
    ("POST", "/api/character/attributes"),
    ("POST", "/api/character/relationships-summary"),
    ("GET", "/api/presets"),
    ("POST", "/api/presets"),
    ("GET", "/api/presets/{preset_id}"),
    ("DELETE", "/api/presets/{preset_id}"),
    ("GET", "/api/friends"),
    ("GET", "/api/friends/requests"),
    ("POST", "/api/friends/request"),
    ("POST", "/api/friends/respond"),
    ("DELETE", "/api/friends/{friend_user_id}"),
    ("POST", "/api/music/recommend"),
    ("GET", "/api/music/song-url"),
    ("GET", "/api/music/search"),
    ("GET", "/api/music/stream/{song_id}"),
}


DEPRECATED_BROWSER_API_ROUTES = {
    ("GET", "/api/games/{game_id}/round-scenes/{round_number}"),
    ("POST", "/api/games/{game_id}/regenerate/stream"),
    ("POST", "/api/games/{game_id}/rewrite/stream"),
    ("POST", "/api/games/{game_id}/choices/stream"),
    ("POST", "/api/games/{game_id}/choices/custom/stream"),
    ("POST", "/api/images/{image_id}/regenerate"),
}


def test_browser_api_contract_routes_exist_without_starting_browser() -> None:
    registered = _registered_routes()

    assert REQUIRED_BROWSER_API_ROUTES <= registered


def test_deprecated_browser_api_routes_stay_absent_without_starting_browser() -> None:
    registered = _registered_routes()

    assert DEPRECATED_BROWSER_API_ROUTES.isdisjoint(registered)


def test_shift_left_route_contract_is_wired_before_e2e() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    route_contract = "tests/test_shift_left_e2e_contract_no_mock.py"

    assert route_contract in script
    assert "openspec validate shift-left-e2e-contract-gates --strict" in script
    assert script.index(route_contract) < script.index("run_e2e_browser || ((failed++))")
    assert script.index("run_contract || ((failed++))") < script.index(
        "run_e2e_browser || ((failed++))"
    )
