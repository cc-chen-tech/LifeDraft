"""契约测试 — GameState round_info 字段一致性

验证 get_game_state 返回的 round_info.current_round
正确映射自 player_state.current_round，而非不存在的 game_loop.current_round。
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestGameStateRoundContract:
    """契约测试：GameState round_info 字段"""

    @patch("src.api.routers.gameplay.summary.session_service")
    def test_current_round_from_player_state(self, mock_session_service):
        """current_round 必须反映 player_state.current_round 的值"""
        session = MagicMock()
        game_loop = MagicMock()

        # player_state 有 current_round = 2
        game_loop.player_state.to_dict.return_value = {
            "age": 32,
            "week": 51,
            "current_round": 2,
            "rounds_per_week": 3,
        }
        game_loop.is_game_over.return_value = False
        game_loop.current_event = None

        # 故意不设 game_loop.current_round（模拟 bug 条件）
        if hasattr(game_loop, "current_round"):
            delattr(game_loop, "current_round")

        session.game_loop = game_loop
        mock_session_service.get_or_restore.return_value = session

        response = client.get("/api/games/1/state")
        assert response.status_code == 200
        data = response.json()

        assert "round_info" in data
        assert data["round_info"]["current_round"] == 2, (
            f"current_round 应从 player_state 读取为 2，"
            f"实际为 {data['round_info']['current_round']}"
        )

    @patch("src.api.routers.gameplay.summary.session_service")
    def test_current_round_defaults_to_zero_when_missing(self, mock_session_service):
        """player_state 缺少 current_round 时默认返回 0"""
        session = MagicMock()
        game_loop = MagicMock()
        game_loop.player_state.to_dict.return_value = {
            "age": 32,
            "week": 51,
            # current_round 故意缺失
        }
        game_loop.is_game_over.return_value = False
        game_loop.current_event = None

        session.game_loop = game_loop
        mock_session_service.get_or_restore.return_value = session

        response = client.get("/api/games/1/state")
        assert response.status_code == 200
        data = response.json()

        assert data["round_info"]["current_round"] == 0

    @patch("src.api.routers.gameplay.summary.session_service")
    def test_week_advances_in_progress(self, mock_session_service):
        """progress.week 应正确反映 player_state.week"""
        session = MagicMock()
        game_loop = MagicMock()
        game_loop.player_state.to_dict.return_value = {
            "age": 33,
            "week": 52,
            "current_round": 1,
        }
        game_loop.is_game_over.return_value = False
        game_loop.current_event = None

        session.game_loop = game_loop
        mock_session_service.get_or_restore.return_value = session

        response = client.get("/api/games/1/state")
        assert response.status_code == 200
        data = response.json()

        assert data["progress"]["week"] == 52
        assert data["progress"]["age"] == 33
