"""Tests for durable event-generation routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.models import EventOption, GameEvent
from src.api.routers.gameplay.events import _is_api_contract_probe, _require_session, router
from src.api.services.event_generation_operation import EventGenerationKey
from src.api.session_store import GameLoopSession


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/games")
    return TestClient(app)


def _event(story: str = "测试事件") -> GameEvent:
    return GameEvent(
        event_description=story,
        options=[
            EventOption(text="选项1", effects={}),
            EventOption(text="选项2", effects={}),
        ],
    )


class TestRequireSession:
    @patch("src.api.routers.gameplay.events.session_service")
    def test_require_session_returns_session(self, mock_service):
        mock_session = MagicMock()
        mock_service.get_or_restore.return_value = mock_session

        result = _require_session(1, 42)

        assert result == mock_session
        mock_service.get_or_restore.assert_called_once_with(1, 42)


class TestE2EContractProbe:
    def test_authenticated_playwright_request_is_not_a_contract_probe(self, monkeypatch):
        monkeypatch.setenv("E2E_CONTRACT_PROBE_FAST", "1")
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/games/1/event-sync",
            "headers": [
                (b"user-agent", b"Playwright/1.58"),
                (b"cookie", b"access_token=e2e-token"),
            ],
        }

        from starlette.requests import Request

        assert _is_api_contract_probe(Request(scope)) is False

    def test_unauthenticated_playwright_request_is_a_contract_probe(self, monkeypatch):
        monkeypatch.setenv("E2E_CONTRACT_PROBE_FAST", "1")
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/games/1/event-sync",
            "headers": [(b"user-agent", b"Playwright/1.58")],
        }

        from starlette.requests import Request

        assert _is_api_contract_probe(Request(scope)) is True


class TestGenerateEventEndpoint:
    @patch("src.api.routers.gameplay.events._require_session")
    def test_generate_event_game_over(self, mock_require, client):
        mock_session = MagicMock()
        mock_session.game_loop.is_game_over.return_value = True
        mock_require.return_value = mock_session

        response = client.get("/games/1/event")

        assert response.status_code == 400

    @patch("src.api.routers.gameplay.events._require_session")
    def test_generate_event_has_existing_event(self, mock_require, client):
        mock_session = MagicMock()
        mock_session.sse_cache = []
        mock_session.game_loop.is_game_over.return_value = False
        mock_session.game_loop.current_event = _event()
        mock_require.return_value = mock_session

        response = client.get("/games/1/event")

        assert response.status_code == 200
        assert "event: complete" in response.text

    @patch("src.api.routers.gameplay.events._require_session")
    def test_unfinished_event_delegates_to_durable_stream(self, mock_require, client):
        mock_session = MagicMock()
        mock_session.game_loop.is_game_over.return_value = False
        mock_session.game_loop.current_event = None
        mock_require.return_value = mock_session

        async def fake_stream(game_loop, game_id, session, last_event_id):
            assert game_loop is mock_session.game_loop
            assert game_id == 1
            assert session is mock_session
            assert last_event_id is None
            yield 'event: status\ndata: {"phase":"resuming"}\n\n'
            yield 'event: complete\ndata: {"event_description":"完成"}\n\n'

        with patch(
            "src.api.routers.gameplay.events.stream_round_event", new=fake_stream
        ) as durable_stream:
            response = client.get("/games/1/event")

        assert response.status_code == 200
        assert "event: complete" in response.text
        assert durable_stream is fake_stream


class TestGenerateEventSync:
    @patch("src.api.routers.gameplay.events._require_session")
    def test_generate_event_sync_game_over(self, mock_require, client):
        mock_session = MagicMock()
        mock_session.game_loop.is_game_over.return_value = True
        mock_require.return_value = mock_session

        response = client.post("/games/1/event-sync")

        assert response.status_code == 400

    @patch("src.api.routers.gameplay.events._require_session")
    def test_sync_reuses_completed_operation(self, mock_require, client):
        game_loop = MagicMock()
        game_loop.is_game_over.return_value = False
        game_loop.current_event = None
        game_loop.player_state.week = 0
        game_loop.player_state.current_round = 0
        session = GameLoopSession(game_loop=game_loop, game_id=1)
        operation, _ = session.event_generation.get_or_create(
            EventGenerationKey(1, 0, 0, "event")
        )
        operation.complete(_event("已完成的共享结果"))
        mock_require.return_value = session

        response = client.post("/games/1/event-sync")

        assert response.status_code == 200
        assert response.json()["event_description"] == "已完成的共享结果"
        game_loop.generate_round_event.assert_not_called()
