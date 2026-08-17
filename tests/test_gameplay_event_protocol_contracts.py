"""Provider-free gameplay event route safeguard contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request

from src.api.routers.gameplay.events import (
    SSEConnectionManager,
    _parse_last_event_id,
    _require_resume_view_acknowledged,
)

pytestmark = [pytest.mark.unit]



def _request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw_headers})


def test_sse_connection_manager_enforces_user_and_global_limits():
    manager = SSEConnectionManager(max_per_user=2, max_global=3)

    assert manager.acquire("user-a") is True
    assert manager.acquire("user-a") is True
    assert manager.acquire("user-a") is False
    assert manager.acquire("user-b") is True
    assert manager.acquire("user-c") is False


def test_sse_connection_release_restores_capacity_without_underflow():
    manager = SSEConnectionManager(max_per_user=1, max_global=1)

    manager.release("unknown-user")
    assert manager.acquire("user-a") is True
    manager.release("user-a")
    manager.release("user-a")

    assert manager.acquire("user-b") is True


@pytest.mark.parametrize("phase", ["result", "summary", "ending"])
def test_saved_terminal_resume_view_blocks_event_generation(phase: str):
    game_loop = SimpleNamespace(player_state=SimpleNamespace(resume_view={"phase": phase}))

    with pytest.raises(HTTPException) as exc_info:
        _require_resume_view_acknowledged(game_loop)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"] == "saved_view_pending"


@pytest.mark.parametrize("resume_view", [None, {}, {"phase": "opening"}])
def test_non_terminal_resume_views_allow_event_generation(resume_view: object):
    _require_resume_view_acknowledged(
        SimpleNamespace(player_state=SimpleNamespace(resume_view=resume_view))
    )


def test_last_event_id_parser_preserves_valid_cursor_and_rejects_invalid_input():
    assert _parse_last_event_id(_request()) is None
    assert _parse_last_event_id(_request({"Last-Event-ID": "41"})) == 41

    with pytest.raises(HTTPException) as exc_info:
        _parse_last_event_id(_request({"Last-Event-ID": "forty-one"}))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid Last-Event-ID"
