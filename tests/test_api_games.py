"""Tests for games API routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# API tests - games endpoints
pytestmark = pytest.mark.api

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock GameDatabase."""
    db = MagicMock()
    with patch("src.api.routers.games.get_db", return_value=db):
        yield db


@pytest.fixture
def mock_session_service():
    """Mock session service."""
    with patch("src.api.routers.games.session_service") as mock:
        yield mock


@pytest.fixture
def mock_session_store():
    """Mock session store."""
    with patch("src.api.routers.games.session_store") as mock:
        yield mock


@pytest.fixture
def auth_headers():
    """Create auth headers with mocked token."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def mock_auth():
    """Mock authentication."""
    with patch("src.api.deps.decode_token") as mock:
        mock.return_value = 1
        yield mock


class TestCreateGame:
    """Tests for POST /api/games."""

    def test_create_game_success(
        self, client, mock_db, mock_session_store, mock_auth, auth_headers
    ):
        """Test creating a new game."""
        with patch("src.api.routers.games.GameInitializer") as MockInit:
            mock_game_loop = MagicMock()
            mock_game_loop.get_state.return_value = MagicMock(
                to_dict=lambda: {"player_name": "Test"}
            )
            mock_game_loop.get_progress.return_value = {"week": 1}
            mock_game_loop.get_round_info.return_value = {"current_round": 0}
            mock_game_loop.current_event = None

            mock_initializer = MagicMock()
            mock_initializer.initialize_game_from_settings.return_value = (
                mock_game_loop,
                1,
            )
            MockInit.return_value = mock_initializer

            response = client.post(
                "/api/games",
                json={
                    "character_settings": {"era": {"era_name": "现代"}},
                    "player_name": "TestPlayer",
                    "life_vision": "Test vision",
                    "language": "zh",
                },
                headers=auth_headers,
            )

            assert response.status_code == 201
            data = response.json()
            # Schema validation: GameStateResponse
            assert "game_id" in data
            assert isinstance(data["game_id"], int)
            assert "player_state" in data
            assert isinstance(data["player_state"], dict)
            assert "progress" in data
            assert isinstance(data["progress"], dict)
            assert "round_info" in data
            assert isinstance(data["round_info"], dict)
            # current_event is optional (can be None)
            assert "current_event" in data
            # Value check
            assert data["game_id"] == 1

    def test_create_game_without_auth(self, client, mock_db, mock_session_store):
        """Test creating game without authentication (anonymous user)."""
        with patch("src.api.routers.games.GameInitializer") as MockInit:
            mock_game_loop = MagicMock()
            mock_game_loop.get_state.return_value = MagicMock(to_dict=lambda: {})
            mock_game_loop.get_progress.return_value = {}
            mock_game_loop.get_round_info.return_value = {}
            mock_game_loop.current_event = None

            mock_initializer = MagicMock()
            mock_initializer.initialize_game_from_settings.return_value = (
                mock_game_loop,
                2,
            )
            MockInit.return_value = mock_initializer

            response = client.post(
                "/api/games",
                json={
                    "character_settings": {},
                    "player_name": "Anon",
                    "life_vision": "",
                    "language": "zh",
                },
            )

            # Should work without auth (anonymous)
            assert response.status_code == 201
            data = response.json()
            # Schema validation: GameStateResponse
            assert "game_id" in data
            assert isinstance(data["game_id"], int)
            assert "player_state" in data
            assert isinstance(data["player_state"], dict)
            assert "progress" in data
            assert "round_info" in data
            assert "current_event" in data

    def test_create_game_invalid_settings(self, client, mock_auth, auth_headers):
        """Test creating game with invalid settings."""
        with patch("src.api.routers.games.GameInitializer") as MockInit:
            mock_initializer = MagicMock()
            mock_initializer.initialize_game_from_settings.side_effect = ValueError(
                "Invalid settings"
            )
            MockInit.return_value = mock_initializer

            response = client.post(
                "/api/games",
                json={
                    "character_settings": {},
                    "player_name": "Test",
                    "life_vision": "",
                    "language": "zh",
                },
                headers=auth_headers,
            )

            assert response.status_code == 400

    def test_create_game_accepts_relationships_list_payload(self, client, mock_db):
        """List-shaped relationships payload should be normalized instead of raising 500."""
        mock_db.create_game.return_value = 77

        response = client.post(
            "/api/games",
            json={
                "character_settings": {
                    "narrative_style_id": "realistic_modern",
                    "era": {"name": "2020年代中国互联网", "period": "2020年代"},
                    "age": {"age": 22},
                    "relationships": [
                        {"name": "陆昊然", "relation": "导师"},
                        {"name": "陈晓雨", "relation": "同学"},
                    ],
                },
                "player_name": "MiniMax生产验证",
                "life_vision": "成为可靠的产品经理",
                "language": "zh",
            },
        )

        assert response.status_code == 201
        assert response.json()["game_id"] == 77
        saved_state = mock_db.create_game.call_args.kwargs["initial_state"]
        assert saved_state["relationships"] == {"陆昊然": 50, "陈晓雨": 50}
        assert saved_state["character_settings"]["relationships"]["key_people"][0]["name"] == "陆昊然"

    def test_create_game_preserves_generated_initial_wealth(self, client, mock_db):
        """Generated wealth should initialize the playable state instead of defaulting to 10000."""
        mock_db.create_game.return_value = 88

        response = client.post(
            "/api/games",
            json={
                "character_settings": {
                    "era": {"name": "2020年代中国互联网", "year": 2024},
                    "age": {"age": 26},
                    "wealth": {
                        "wealth": 40000,
                        "wealth_description": "个人积蓄和父母支持的启动资金共计4万元。",
                    },
                },
                "player_name": "林澈",
                "life_vision": "成为AI协作工具产品经理",
                "language": "zh",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["player_state"]["wealth"] == 40000
        saved_state = mock_db.create_game.call_args.kwargs["initial_state"]
        assert saved_state["wealth"] == 40000

    def test_create_game_preserves_starting_wealth_field_from_character_generator(
        self, client, mock_db
    ):
        """The character wealth generator returns starting_wealth, which must initialize state."""
        mock_db.create_game.return_value = 89

        response = client.post(
            "/api/games",
            json={
                "character_settings": {
                    "era": {"name": "2020年代中国互联网", "year": 2024},
                    "age": {"age": 28},
                    "wealth": {
                        "wealth_level": "中等",
                        "starting_wealth": 50000,
                        "currency": "¥",
                        "currency_name": "元",
                    },
                },
                "player_name": "张若虚",
                "life_vision": "成为可靠的产品经理",
                "language": "zh",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["player_state"]["wealth"] == 50000
        saved_state = mock_db.create_game.call_args.kwargs["initial_state"]
        assert saved_state["wealth"] == 50000


class TestListGames:
    """Tests for GET /api/games."""

    def test_list_games_success(self, client, mock_db, mock_auth, auth_headers):
        """Test listing user's games."""
        from datetime import datetime

        mock_db.list_saved_games.return_value = [
            {
                "game_id": 1,
                "player_name": "Hero",
                "week": 5,
                "age": 23,
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "updated_at": datetime(2024, 1, 2, 12, 0, 0),
                "has_progress": True,
            },
            {
                "game_id": 2,
                "player_name": "Villain",
                "week": 1,
                "age": 22,
                "created_at": datetime(2024, 1, 3, 12, 0, 0),
                "updated_at": None,
                "has_progress": False,
            },
        ]

        response = client.get("/api/games", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Schema validation: List[GameListItem]
        assert isinstance(data, list)
        assert len(data) == 2
        # Validate each item has required GameListItem fields
        for item in data:
            assert "game_id" in item
            assert isinstance(item["game_id"], int)
            assert "player_name" in item
            assert isinstance(item["player_name"], str)
            assert "week" in item
            assert isinstance(item["week"], int)
            assert "age" in item
            assert isinstance(item["age"], int)
            assert "has_progress" in item
            assert isinstance(item["has_progress"], bool)
            # Optional fields should exist (may be None)
            assert "created_at" in item
            assert "updated_at" in item
        # Value checks
        assert data[0]["game_id"] == 1
        assert data[0]["player_name"] == "Hero"
        assert data[0]["has_progress"] is True

    def test_list_games_empty(self, client, mock_db, mock_auth, auth_headers):
        """Test listing games when user has none."""
        mock_db.list_saved_games.return_value = []

        response = client.get("/api/games", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_list_games_no_auth(self, client):
        """Test listing games without authentication."""
        response = client.get("/api/games")
        assert response.status_code == 401

    def test_list_games_with_limit(self, client, mock_db, mock_auth, auth_headers):
        """Test listing games with limit parameter."""
        mock_db.list_saved_games.return_value = []

        response = client.get("/api/games?limit=5", headers=auth_headers)

        assert response.status_code == 200
        mock_db.list_saved_games.assert_called_with(1, limit=5)


class TestLoadGame:
    """Tests for GET /api/games/{game_id}."""

    def test_load_game_success(self, client, mock_db, mock_session_store, mock_auth, auth_headers):
        """Test loading an existing game."""
        mock_db.load_saved_game.return_value = {
            "player_state": {"player_name": "Test"},
            "character_settings": {"era": {"era_description": "现代"}},
        }

        with patch("src.api.routers.games.GameLoop") as MockLoop:
            mock_game_loop = MagicMock()
            mock_game_loop.get_state.return_value = MagicMock(
                to_dict=lambda: {"player_name": "Test"}
            )
            mock_game_loop.get_progress.return_value = {}
            mock_game_loop.get_round_info.return_value = {}
            mock_game_loop.current_event = None
            MockLoop.return_value = mock_game_loop

            response = client.get("/api/games/1", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            # Schema validation: GameStateResponse
            assert "game_id" in data
            assert isinstance(data["game_id"], int)
            assert "player_state" in data
            assert isinstance(data["player_state"], dict)
            assert "progress" in data
            assert isinstance(data["progress"], dict)
            assert "round_info" in data
            assert isinstance(data["round_info"], dict)
            assert "current_event" in data
            # Value check
            assert data["game_id"] == 1

    def test_load_game_not_found(self, client, mock_db, mock_auth, auth_headers):
        """Test loading a non-existent game."""
        mock_db.load_saved_game.return_value = None

        response = client.get("/api/games/999", headers=auth_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_load_game_no_auth(self, client):
        """Test loading game without authentication."""
        response = client.get("/api/games/1")
        assert response.status_code == 401


class TestSaveGame:
    """Tests for POST /api/games/{game_id}/save."""

    def test_save_game_success(
        self,
        client,
        mock_db,
        mock_session_store,
        mock_session_service,
        mock_auth,
        auth_headers,
    ):
        """Test saving game progress."""
        mock_session = MagicMock()
        mock_session.game_loop.get_state.return_value = MagicMock()
        mock_session_service.get_or_restore.return_value = mock_session
        mock_db.save_game_progress.return_value = True

        response = client.post("/api/games/1/save", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Schema validation: SaveGameResponse
        assert "success" in data
        assert isinstance(data["success"], bool)
        assert "message" in data
        assert isinstance(data["message"], str)
        assert data["success"] is True

    def test_save_game_no_session(
        self, client, mock_session_store, mock_session_service, mock_auth, auth_headers
    ):
        """Test saving when no active session."""
        from fastapi import HTTPException

        mock_session_service.get_or_restore.side_effect = HTTPException(status_code=404)

        response = client.post("/api/games/1/save", headers=auth_headers)

        assert response.status_code == 404

    def test_save_game_no_state(
        self, client, mock_session_store, mock_session_service, mock_auth, auth_headers
    ):
        """Test saving when no game state."""
        mock_session = MagicMock()
        mock_session.game_loop.get_state.return_value = None
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post("/api/games/1/save", headers=auth_headers)

        assert response.status_code == 400


class TestDeleteGame:
    """Tests for DELETE /api/games/{game_id}."""

    def test_delete_game_success(
        self, client, mock_db, mock_session_store, mock_auth, auth_headers
    ):
        """Test deleting a game."""
        mock_db.delete_saved_game.return_value = True

        response = client.delete("/api/games/1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Schema validation: MessageResponse
        assert "message" in data
        assert isinstance(data["message"], str)
        assert "deleted" in data["message"].lower()

    def test_delete_game_not_found(self, client, mock_db, mock_auth, auth_headers):
        """Test deleting non-existent game."""
        mock_db.delete_saved_game.return_value = False

        response = client.delete("/api/games/999", headers=auth_headers)

        assert response.status_code == 404

    def test_delete_game_no_auth(self, client):
        """Test deleting without authentication."""
        response = client.delete("/api/games/1")
        assert response.status_code == 401


class TestGetActiveGame:
    """Tests for GET /api/games/active - 服务端会话恢复"""

    def test_get_active_game_success(
        self, client, mock_db, mock_session_store, mock_auth, auth_headers
    ):
        """Test getting active game when user has one."""
        # 设置用户有活跃游戏
        mock_db.get_active_game.return_value = 1
        mock_db.load_saved_game.return_value = {
            "player_state": {"player_name": "Test"},
            "character_settings": {"era": {"era_description": "现代"}},
        }

        with patch("src.api.routers.games.GameLoop") as MockLoop:
            mock_game_loop = MagicMock()
            mock_game_loop.get_state.return_value = MagicMock(
                to_dict=lambda: {"player_name": "Test"}
            )
            mock_game_loop.get_progress.return_value = {}
            mock_game_loop.get_round_info.return_value = {}
            mock_game_loop.current_event = None
            MockLoop.return_value = mock_game_loop

            response = client.get("/api/games/active", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            # Schema validation: GameStateResponse
            assert "game_id" in data
            assert isinstance(data["game_id"], int)
            assert "player_state" in data
            assert isinstance(data["player_state"], dict)
            assert "progress" in data
            assert isinstance(data["progress"], dict)
            assert "round_info" in data
            assert isinstance(data["round_info"], dict)
            assert "current_event" in data
            # Value check
            assert data["game_id"] == 1
            # 验证调用了正确的方法
            mock_db.get_active_game.assert_called_once_with(1)
            mock_session_store.put.assert_called_once()

    def test_get_active_game_no_active_game(self, client, mock_db, mock_auth, auth_headers):
        """Test getting active game when user has none."""
        mock_db.get_active_game.return_value = None

        response = client.get("/api/games/active", headers=auth_headers)

        assert response.status_code == 404
        assert "No active game" in response.json()["detail"]

    def test_get_active_game_deleted_game(self, client, mock_db, mock_auth, auth_headers):
        """Test getting active game when the game was deleted."""
        mock_db.get_active_game.return_value = 1
        mock_db.load_saved_game.return_value = None  # 游戏已被删除

        response = client.get("/api/games/active", headers=auth_headers)

        assert response.status_code == 404
        # 应该清除失效的活跃引用
        mock_db.clear_active_game.assert_called_once_with(1)

    def test_get_active_game_no_auth(self, client):
        """Test getting active game without authentication."""
        response = client.get("/api/games/active")
        assert response.status_code == 401


class TestSetActiveGame:
    """Tests for set_active_game functionality."""

    def test_create_game_sets_active(
        self, client, mock_db, mock_session_store, mock_auth, auth_headers
    ):
        """Test that creating a game sets it as active."""
        with patch("src.api.routers.games.GameInitializer") as MockInit:
            mock_game_loop = MagicMock()
            mock_game_loop.get_state.return_value = MagicMock(
                to_dict=lambda: {"player_name": "Test"}
            )
            mock_game_loop.get_progress.return_value = {"week": 1}
            mock_game_loop.get_round_info.return_value = {"current_round": 0}
            mock_game_loop.current_event = None

            mock_initializer = MagicMock()
            mock_initializer.initialize_game_from_settings.return_value = (
                mock_game_loop,
                1,
            )
            MockInit.return_value = mock_initializer

            response = client.post(
                "/api/games",
                json={
                    "character_settings": {"era": {"era_name": "现代"}},
                    "player_name": "TestPlayer",
                    "life_vision": "Test vision",
                    "language": "zh",
                },
                headers=auth_headers,
            )

            assert response.status_code == 201
            # 验证设置了活跃游戏
            mock_db.set_active_game.assert_called_once_with(1, 1)

    def test_load_game_sets_active(
        self, client, mock_db, mock_session_store, mock_auth, auth_headers
    ):
        """Test that loading a game sets it as active."""
        mock_db.load_saved_game.return_value = {
            "player_state": {"player_name": "Test"},
            "character_settings": {"era": {"era_description": "现代"}},
        }

        with patch("src.api.routers.games.GameLoop") as MockLoop:
            mock_game_loop = MagicMock()
            mock_game_loop.get_state.return_value = MagicMock(
                to_dict=lambda: {"player_name": "Test"}
            )
            mock_game_loop.get_progress.return_value = {}
            mock_game_loop.get_round_info.return_value = {}
            mock_game_loop.current_event = None
            MockLoop.return_value = mock_game_loop

            response = client.get("/api/games/1", headers=auth_headers)

            assert response.status_code == 200
            # 验证设置了活跃游戏
            mock_db.set_active_game.assert_called_once_with(1, 1)

    def test_delete_game_clears_active(
        self, client, mock_db, mock_session_store, mock_auth, auth_headers
    ):
        """Test that deleting the active game clears it."""
        mock_db.get_active_game.return_value = 1  # 删除的是活跃游戏
        mock_db.delete_saved_game.return_value = True

        response = client.delete("/api/games/1", headers=auth_headers)

        assert response.status_code == 200
        # 验证清除了活跃游戏
        mock_db.clear_active_game.assert_called_once_with(1)

    def test_delete_other_game_keeps_active(
        self, client, mock_db, mock_session_store, mock_auth, auth_headers
    ):
        """Test that deleting another game doesn't clear active."""
        mock_db.get_active_game.return_value = 2  # 活跃游戏是另一个
        mock_db.delete_saved_game.return_value = True

        response = client.delete("/api/games/1", headers=auth_headers)

        assert response.status_code == 200
        # 不应该清除活跃游戏
        mock_db.clear_active_game.assert_not_called()
