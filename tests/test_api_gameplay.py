"""Tests for gameplay API routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# API tests - gameplay endpoints
pytestmark = pytest.mark.api

from src.api.main import app  # noqa: E402
from src.api.services.event_generation_operation import (  # noqa: E402
    EventGenerationCoordinator,
    EventGenerationKey,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create auth headers."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def mock_auth():
    """Mock authentication."""
    with patch("src.api.deps.decode_token") as mock:
        mock.return_value = 1
        yield mock


@pytest.fixture
def mock_session():
    """Create a mock game session."""
    session = MagicMock()
    session.game_loop = MagicMock()
    session.game_loop.is_game_over.return_value = False
    session.game_loop.current_event = None
    session.game_loop._generating = False
    session.game_loop.player_state = MagicMock()
    session.game_loop.player_state.week = 0
    session.game_loop.player_state.current_round = 0
    session.game_loop.player_state.to_dict.return_value = {}
    session.game_loop.current_round = 0
    session.sse_cache = []
    session.event_generation = EventGenerationCoordinator()
    session.language = "zh"
    return session


@pytest.fixture
def mock_session_store():
    """Mock session store for all gameplay submodules."""
    # Patch at the source - all imports will use this mock
    with patch("src.api.session_store.session_store") as mock:
        yield mock


@pytest.fixture
def mock_session_service(mock_session):
    """Mock session service (used by endpoints to get sessions)."""
    with patch("src.api.services.session_service.session_service.get_or_restore") as mock:
        yield mock


@pytest.fixture
def mock_db():
    """Mock database."""
    with patch("src.api.routers.gameplay.summary.get_db") as mock:
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=MagicMock())
        mock_context.__exit__ = MagicMock(return_value=False)
        mock.return_value = mock_context
        yield mock


class TestGetGameState:
    """Tests for GET /api/gameplay/{game_id}/state."""

    def test_get_state_success(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test getting game state."""
        mock_session.game_loop.player_state.to_dict.return_value = {
            "player_name": "Test",
            "age": 22,
            "week": 5,
        }
        mock_session.game_loop.current_round = 1
        mock_session_service.return_value = mock_session

        response = client.get("/api/games/1/state", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Schema validation: game state response
        assert "game_id" in data
        assert isinstance(data["game_id"], int)
        assert "player_state" in data
        assert isinstance(data["player_state"], dict)
        assert data["game_id"] == 1

    def test_get_state_no_session(self, client, auth_headers, mock_auth, mock_session_service):
        """Test getting state without active session."""
        from fastapi import HTTPException

        mock_session_service.side_effect = HTTPException(status_code=404, detail="Game not found")
        response = client.get("/api/games/1/state", headers=auth_headers)
        assert response.status_code == 404


class TestMakeChoice:
    """Tests for POST /api/gameplay/{game_id}/choice."""

    def test_make_choice_invalid_index(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test making choice with invalid option index."""
        mock_event = MagicMock()
        mock_event.options = [{"text": "Option 1"}, {"text": "Option 2"}]
        mock_session.game_loop.current_event = mock_event
        mock_session_service.return_value = mock_session

        response = client.post(
            "/api/games/1/choice", json={"option_index": 5}, headers=auth_headers
        )

        assert response.status_code == 400

    def test_make_choice_no_session(self, client, auth_headers, mock_auth, mock_session_service):
        """Test making choice without active session."""
        from fastapi import HTTPException

        mock_session_service.side_effect = HTTPException(status_code=404, detail="Game not found")
        response = client.post(
            "/api/games/1/choice", json={"option_index": 0}, headers=auth_headers
        )
        assert response.status_code == 404


class TestCustomChoice:
    """Tests for POST /api/gameplay/{game_id}/custom-choice."""

    def test_custom_choice_no_session(self, client, auth_headers, mock_auth, mock_session_service):
        """Test custom choice without active session."""
        from fastapi import HTTPException

        mock_session_service.side_effect = HTTPException(status_code=404, detail="Game not found")
        response = client.post(
            "/api/games/1/custom-choice",
            json={"custom_text": "My custom action"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_custom_choice_empty_text(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test custom choice with empty text."""
        mock_session_service.return_value = mock_session
        response = client.post(
            "/api/games/1/custom-choice", json={"custom_text": ""}, headers=auth_headers
        )
        assert response.status_code == 422


class TestGenerateSummary:
    """Tests for POST /api/gameplay/{game_id}/summary."""

    def test_generate_summary_success(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test generating summary."""
        mock_session.game_loop.generate_summary.return_value = {
            "summary_text": "Your journey so far...",
            "start_week": 1,
            "end_week": 10,
        }
        mock_session_service.return_value = mock_session

        response = client.post("/api/games/1/summary", json={"weeks": 10}, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Schema validation: summary response
        assert "summary_text" in data
        assert isinstance(data["summary_text"], str)
        assert len(data["summary_text"]) > 0

    def test_generate_summary_no_session(
        self, client, auth_headers, mock_auth, mock_session_service
    ):
        """Test generating summary without session."""
        from fastapi import HTTPException

        mock_session_service.side_effect = HTTPException(status_code=404, detail="Game not found")
        response = client.post("/api/games/1/summary", json={"weeks": 10}, headers=auth_headers)
        assert response.status_code == 404

    def test_generate_summary_error(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test summary generation with AI error - should fallback gracefully."""
        # Mock AI generator to raise error, but endpoint has fallback
        mock_session.game_loop.ai_generator.generate_completion.side_effect = Exception("AI error")

        # Set real values for player_state (needed for format strings in fallback)
        mock_player = MagicMock()
        mock_player.player_name = "Test"
        mock_player.age = 25
        mock_player.week = 10
        mock_player.wealth = 10000
        mock_player.knowledge = 50
        mock_session.game_loop.player_state = mock_player
        mock_session_service.return_value = mock_session

        # Mock db to return some story history
        with patch("src.api.routers.gameplay.summary.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.get_story_history.return_value = [
                {"week": 1, "story_text": "A story.", "choice_text": "A choice."}
            ]
            mock_get_db.return_value = mock_db

            response = client.post("/api/games/1/summary", json={"weeks": 10}, headers=auth_headers)
        # Should return 200 with fallback summary
        assert response.status_code == 200
        data = response.json()
        # Schema validation: summary response (fallback)
        assert "summary_text" in data
        assert isinstance(data["summary_text"], str)


class TestGetEnding:
    """Tests for GET /api/gameplay/{game_id}/ending."""

    def test_get_ending_success(
        self,
        client,
        auth_headers,
        mock_auth,
        mock_session_service,
        mock_session,
        mock_db,
    ):
        """Test getting game ending."""
        mock_session.game_loop.is_game_over.return_value = True
        mock_session.game_loop.get_state.return_value = MagicMock()
        mock_session_service.return_value = mock_session

        with patch("src.api.routers.gameplay.summary.EndingEvaluator") as MockEval:
            mock_evaluator = MagicMock()
            mock_evaluator.evaluate_ending.return_value = {
                "ending_type": "happy",
                "summary": "A life well lived",
                "final_stats": {},
                "achievements": [],
            }
            MockEval.return_value = mock_evaluator

            response = client.get("/api/games/1/ending", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            # Schema validation: ending response
            assert "ending_type" in data
            assert isinstance(data["ending_type"], str)
            assert "summary" in data
            assert isinstance(data["summary"], str)
            assert "final_stats" in data
            assert isinstance(data["final_stats"], dict)
            assert "achievements" in data
            assert isinstance(data["achievements"], list)
            # Value check
            assert data["ending_type"] == "happy"

    def test_get_ending_game_not_over(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test getting ending when game not over."""
        mock_session.game_loop.is_game_over.return_value = False
        mock_session_service.return_value = mock_session

        response = client.get("/api/games/1/ending", headers=auth_headers)

        assert response.status_code == 400
        assert "not over" in response.json()["detail"].lower()

    def test_get_ending_no_session(self, client, auth_headers, mock_auth, mock_session_service):
        """Test getting ending without session."""
        from fastapi import HTTPException

        mock_session_service.side_effect = HTTPException(status_code=404, detail="Game not found")
        response = client.get("/api/games/1/ending", headers=auth_headers)
        assert response.status_code == 404


class TestEventSync:
    """Tests for POST /api/gameplay/{game_id}/event-sync."""

    def test_event_sync_existing_event(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test sync endpoint returns existing event."""
        mock_event = MagicMock()
        mock_event.options = [{"text": "Option 1"}]
        mock_event.model_dump.return_value = {
            "event_description": "Something happened",
            "options": [{"text": "Option 1"}],
        }
        mock_session.game_loop.current_event = mock_event
        mock_session.game_loop.is_game_over.return_value = False
        mock_session_service.return_value = mock_session

        response = client.post("/api/games/1/event-sync", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Schema validation: event sync response
        assert "event_description" in data
        assert isinstance(data["event_description"], str)
        assert "options" in data
        assert isinstance(data["options"], list)

    def test_event_sync_game_over(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test sync endpoint when game is over."""
        mock_session.game_loop.is_game_over.return_value = True
        mock_session.game_loop.current_event = None
        mock_session_service.return_value = mock_session

        response = client.post("/api/games/1/event-sync", headers=auth_headers)
        assert response.status_code == 400

    def test_event_sync_reuses_completed_generation_operation(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Sync fallback reuses the durable operation instead of starting another."""
        from src.ai.models import EventOption, GameEvent

        mock_session.game_loop.is_game_over.return_value = False
        mock_session.game_loop.current_event = None
        event = GameEvent(
            event_description="Shared completed event",
            options=[
                EventOption(text="Option 1", effects={}),
                EventOption(text="Option 2", effects={}),
            ],
        )
        operation, _ = mock_session.event_generation.get_or_create(
            EventGenerationKey(1, 0, 0, "event")
        )
        operation.complete(event)
        mock_session_service.return_value = mock_session

        response = client.post("/api/games/1/event-sync", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["event_description"] == "Shared completed event"
        mock_session.game_loop.generate_round_event.assert_not_called()


class TestChoiceSync:
    """Tests for POST /api/gameplay/{game_id}/choice-sync."""

    def test_choice_sync_invalid_index(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test sync choice with invalid index."""
        mock_event = MagicMock()
        mock_event.options = [{"text": "Option 1"}]
        mock_session.game_loop.current_event = mock_event
        mock_session_service.return_value = mock_session

        response = client.post(
            "/api/games/1/choice-sync", json={"option_index": 10}, headers=auth_headers
        )
        assert response.status_code == 400


class TestCustomChoiceSync:
    """Tests for POST /api/gameplay/{game_id}/custom-choice-sync."""

    def test_custom_choice_sync_empty(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test custom choice sync with empty text."""
        mock_session_service.return_value = mock_session
        response = client.post(
            "/api/games/1/custom-choice-sync",
            json={"custom_text": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestSummaryWeekRange:
    """验证总结周期范围使用 min/max 而非首尾元素。

    Bug 背景：当 story_history 中的 week 不是按顺序排列时
    （如 [5, 1, 3]），使用首尾元素会导致错误的 start_week/end_week。
    修复后使用 min/max 计算。
    """

    def test_summary_unordered_weeks_uses_min_max(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """无序 week 数据应正确计算 start_week 和 end_week。"""
        # 构建包含无序 week 的 round_history
        mock_player = MagicMock()
        mock_player.player_name = "Test"
        mock_player.age = 25
        mock_player.week = 5
        mock_player.wealth = 10000
        mock_player.knowledge = 50
        mock_player.energy = 80
        mock_player.mood = 70
        mock_player.round_history = [
            {
                "week": 4,
                "round": 0,
                "event_description": "第五周事件",
                "story_continuation": "故事5",
                "choice": "选择5",
            },
            {
                "week": 0,
                "round": 0,
                "event_description": "第一周事件",
                "story_continuation": "故事1",
                "choice": "选择1",
            },
            {
                "week": 2,
                "round": 0,
                "event_description": "第三周事件",
                "story_continuation": "故事3",
                "choice": "选择3",
            },
        ]
        mock_player.decision_history = []
        mock_session.game_loop.player_state = mock_player
        mock_session.game_loop.ai_generator.generate_completion.return_value = "这是一段总结。"
        mock_session_service.return_value = mock_session

        response = client.post("/api/games/1/summary", json={}, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # week 是 0-based，显示时 +1
        # min(4,0,2)=0, max(4,0,2)=4 → start_week=1, end_week=5
        assert (
            data["start_week"] == 1
        ), f"start_week 应为 1（min week 0 + 1），实际为 {data['start_week']}"
        assert (
            data["end_week"] == 5
        ), f"end_week 应为 5（max week 4 + 1），实际为 {data['end_week']}"

    def test_summary_single_week(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """只有一周数据时 start_week == end_week。"""
        mock_player = MagicMock()
        mock_player.player_name = "Test"
        mock_player.age = 25
        mock_player.week = 3
        mock_player.wealth = 10000
        mock_player.knowledge = 50
        mock_player.energy = 80
        mock_player.mood = 70
        mock_player.round_history = [
            {
                "week": 2,
                "round": 0,
                "event_description": "事件",
                "story_continuation": "故事",
                "choice": "选择",
            },
            {
                "week": 2,
                "round": 1,
                "event_description": "事件2",
                "story_continuation": "故事2",
                "choice": "选择2",
            },
        ]
        mock_player.decision_history = []
        mock_session.game_loop.player_state = mock_player
        mock_session.game_loop.ai_generator.generate_completion.return_value = "总结。"
        mock_session_service.return_value = mock_session

        response = client.post("/api/games/1/summary", json={}, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # week=2 (0-based) → display week=3
        assert data["start_week"] == 3
        assert data["end_week"] == 3

    def test_summary_empty_history_fallback(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """空 round_history 应返回默认总结。"""
        mock_player = MagicMock()
        mock_player.player_name = "Test"
        mock_player.age = 25
        mock_player.week = 0
        mock_player.wealth = 5000
        mock_player.knowledge = 30
        mock_player.energy = 100
        mock_player.mood = 100
        mock_player.round_history = []
        mock_player.decision_history = []
        mock_session.game_loop.player_state = mock_player
        mock_session_service.return_value = mock_session

        response = client.post("/api/games/1/summary", json={}, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "summary_text" in data
        assert "刚刚开始" in data["summary_text"]
