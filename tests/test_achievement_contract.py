"""Achievement & Life Review API Contract Tests

验证成就系统和人生回顾卡片的 API 响应格式。
Layer 3: 契约测试 — 字段名、类型、必填性。
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestAchievementAPIContract:
    """测试成就相关 API 契约"""

    def test_ending_api_returns_life_review_field(self):
        """结局 API 响应应包含 life_review 字段"""
        with patch("src.api.routers.gameplay.summary.session_service") as mock_service:
            mock_session = MagicMock()
            mock_game_loop = MagicMock()
            mock_game_loop.is_game_over.return_value = True
            mock_game_loop.get_state.return_value = MagicMock(
                energy=50,
                mood=50,
                knowledge=50,
                wealth=5000,
                relationships={},
                decision_history=[],
                week=10,
                round_history=[],
                character_settings={},
                four_week_summaries=[],
                age=25,
            )
            mock_game_loop.ai_generator = None
            mock_session.game_loop = mock_game_loop
            mock_session.language = "zh"
            mock_service.get_or_restore.return_value = mock_session

            response = client.get("/api/games/1/ending")
            assert response.status_code == 200
            data = response.json()
            assert "life_review" in data
            review = data["life_review"]
            assert "personality_labels" in review
            assert "key_turning_points" in review
            assert "resource_curves" in review
            assert "achievement_badge_wall" in review
            assert "relationship_network" in review
            assert "life_motto" in review

    def test_ending_api_achievements_structure(self):
        """成就字段应为结构化对象列表"""
        with patch("src.api.routers.gameplay.summary.session_service") as mock_service:
            mock_session = MagicMock()
            mock_game_loop = MagicMock()
            mock_game_loop.is_game_over.return_value = True
            mock_game_loop.get_state.return_value = MagicMock(
                energy=50,
                mood=50,
                knowledge=50,
                wealth=5000,
                relationships={},
                decision_history=[{"choice": "A"}] * 30,
                week=10,
                round_history=[],
                character_settings={},
                four_week_summaries=[],
                age=25,
            )
            mock_game_loop.ai_generator = None
            mock_session.game_loop = mock_game_loop
            mock_session.language = "zh"
            mock_service.get_or_restore.return_value = mock_session

            response = client.get("/api/games/1/ending")
            assert response.status_code == 200
            data = response.json()
            achievements = data.get("achievements", {})
            assert "list" in achievements
            assert "count" in achievements
            assert isinstance(achievements["list"], list)
            assert isinstance(achievements["count"], int)
            # 新结构：每个成就是对象
            for ach in achievements["list"]:
                assert isinstance(ach, dict)
                assert "id" in ach
                assert "name" in ach
                assert "rarity" in ach
                assert ach["rarity"] in ["common", "rare", "epic", "legendary"]

    def test_ending_api_game_not_over_returns_400(self):
        """游戏未结束时返回 400"""
        with patch("src.api.routers.gameplay.summary.session_service") as mock_service:
            mock_session = MagicMock()
            mock_game_loop = MagicMock()
            mock_game_loop.is_game_over.return_value = False
            mock_session.game_loop = mock_game_loop
            mock_service.get_or_restore.return_value = mock_session

            response = client.get("/api/games/1/ending")
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data

    def test_life_review_resource_curves_structure(self):
        """resource_curves contains the three active resources."""
        with patch("src.api.routers.gameplay.summary.session_service") as mock_service:
            mock_session = MagicMock()
            mock_game_loop = MagicMock()
            mock_game_loop.is_game_over.return_value = True
            mock_game_loop.get_state.return_value = MagicMock(
                energy=50,
                mood=50,
                knowledge=50,
                relationships={},
                decision_history=[],
                week=10,
                round_history=[],
                character_settings={},
                four_week_summaries=[],
                age=25,
            )
            mock_game_loop.ai_generator = None
            mock_session.game_loop = mock_game_loop
            mock_session.language = "zh"
            mock_service.get_or_restore.return_value = mock_session

            response = client.get("/api/games/1/ending")
            data = response.json()
            curves = data["life_review"]["resource_curves"]
            assert "energy" in curves
            assert "mood" in curves
            assert "knowledge" in curves
            assert set(curves) == {"energy", "mood", "knowledge"}
            assert isinstance(curves["energy"], list)
            assert isinstance(curves["mood"], list)
            assert isinstance(curves["knowledge"], list)

    def test_life_review_badge_wall_structure(self):
        """achievement_badge_wall 条目包含所需字段"""
        with patch("src.api.routers.gameplay.summary.session_service") as mock_service:
            mock_session = MagicMock()
            mock_game_loop = MagicMock()
            mock_game_loop.is_game_over.return_value = True
            mock_game_loop.get_state.return_value = MagicMock(
                energy=50,
                mood=50,
                knowledge=50,
                wealth=5000,
                relationships={},
                decision_history=[{"choice": "A"}] * 30,
                week=10,
                round_history=[],
                character_settings={},
                four_week_summaries=[],
                age=25,
            )
            mock_game_loop.ai_generator = None
            mock_session.game_loop = mock_game_loop
            mock_session.language = "zh"
            mock_service.get_or_restore.return_value = mock_session

            response = client.get("/api/games/1/ending")
            data = response.json()
            badges = data["life_review"]["achievement_badge_wall"]
            assert isinstance(badges, list)
            for badge in badges:
                assert "id" in badge
                assert "name" in badge
                assert "rarity" in badge
                assert badge["rarity"] in ["common", "rare", "epic", "legendary"]
                assert "unlocked_at_week" in badge
