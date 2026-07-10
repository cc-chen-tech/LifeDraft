"""Retirement contract for the removed friends product surface."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


pytestmark = pytest.mark.api
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("GET", "/api/friends", None),
        ("GET", "/api/friends/requests", None),
        ("POST", "/api/friends/request", {"to_public_id": "ABC123"}),
        ("POST", "/api/friends/respond", {"request_id": 1, "accept": True}),
        ("DELETE", "/api/friends/2", None),
        ("POST", "/api/friends/requests", {"to_public_id": "ABC123"}),
        ("PUT", "/api/friends/requests/1", {"accept": True}),
    ],
)
def test_retired_friend_routes_return_not_found(
    client: TestClient,
    method: str,
    path: str,
    json: dict[str, object] | None,
) -> None:
    response = client.request(method, path, json=json)

    assert response.status_code == 404


def test_retired_friend_routes_are_absent_from_openapi() -> None:
    paths = app.openapi()["paths"]

    assert all(not path.startswith("/api/friends") for path in paths)


def test_friends_router_source_is_removed() -> None:
    assert not (ROOT / "src" / "api" / "routers" / "friends.py").exists()


def test_app_does_not_import_or_register_friends_router() -> None:
    main_source = (ROOT / "src" / "api" / "main.py").read_text(encoding="utf-8")

    assert "friends" not in main_source
