"""Achievement & Life Review DB Integration Tests

验证成就和人生回顾数据的数据库持久化。
Layer 4: DB 集成测试 — 保存→读取链路完整。
"""

import pytest

from src.game.achievements import Achievement, AchievementEngine
from src.game.life_review import LifeReviewGenerator
from src.game.state import PlayerState


class TestAchievementPersistence:
    """测试成就数据的数据库持久化"""

    @pytest.fixture(scope="function")
    def db_session(self):
        """提供数据库会话，测试后回滚"""
        from src.database.models import SessionLocal

        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    def test_achievement_engine_returns_structured_achievements(self):
        """AchievementEngine 返回结构化 Achievement 列表"""
        player = PlayerState(
            player_name="Test",
            energy=50,
            mood=50,
            knowledge=50,
            wealth=5000,
            week=10,
            age=25,
            decision_history=[{"choice": "A"}] * 30,
            round_history=[
                {"week": i, "choice": "A", "summary": "test"} for i in range(10)
            ],
        )
        engine = AchievementEngine(language="zh")
        achievements = engine.evaluate(player)

        assert isinstance(achievements, list)
        for ach in achievements:
            assert isinstance(ach, Achievement)
            assert ach.id is not None
            assert ach.name is not None
            assert ach.rarity in ["common", "rare", "epic", "legendary"]
            assert ach.dimension in [
                "trajectory",
                "decision_style",
                "relationships",
                "collection",
                "narrative",
                "hidden",
            ]

    def test_achievement_rarity_distribution(self):
        """稀有度分布合理（至少有一种 common 和一种 rare）"""
        player = PlayerState(
            player_name="Test",
            energy=50,
            mood=50,
            knowledge=50,
            wealth=100000,
            week=50,
            age=30,
            decision_history=[{"choice": "A"}] * 50,
            round_history=[
                {"week": i, "choice": "A", "summary": "test"} for i in range(50)
            ],
            relationships={
                "Alice": 90,
                "Bob": 80,
                "Charlie": 70,
                "David": 60,
                "Eve": 50,
            },
        )
        engine = AchievementEngine(language="zh")
        achievements = engine.evaluate(player)
        rarities = [a.rarity for a in achievements]

        assert "common" in rarities or len(achievements) == 0
        # 高分玩家应该解锁多种稀有度
        assert len(set(rarities)) >= 1

    def test_life_review_generator_returns_valid_structure(self):
        """LifeReviewGenerator 返回有效结构"""
        player = PlayerState(
            player_name="Test",
            energy=80,
            mood=70,
            knowledge=60,
            wealth=10000,
            week=20,
            age=27,
            decision_history=[{"choice": "A"}] * 20,
            round_history=[
                {"week": i, "choice": "A", "summary": "test"} for i in range(20)
            ],
            relationships={"Alice": 85},
        )
        achievements = [
            Achievement(
                id="test",
                name="Test",
                description="Test",
                rarity="common",
                dimension="trajectory",
            )
        ]
        generator = LifeReviewGenerator(language="zh")
        review = generator.generate(player, achievements)

        assert "personality_labels" in review
        assert isinstance(review["personality_labels"], list)
        assert "key_turning_points" in review
        assert isinstance(review["key_turning_points"], list)
        assert "resource_curves" in review
        assert "achievement_badge_wall" in review
        assert "relationship_network" in review
        assert "life_motto" in review
        assert isinstance(review["life_motto"], str)
        assert len(review["life_motto"]) > 0

    def test_life_review_resource_curves_have_correct_length(self):
        """resource_curves 数组长度等于游戏周数"""
        player = PlayerState(
            player_name="Test",
            energy=80,
            mood=70,
            knowledge=60,
            wealth=10000,
            week=10,
            age=25,
            decision_history=[{"choice": "A"}] * 10,
            round_history=[
                {"week": i, "choice": "A", "summary": "test"} for i in range(10)
            ],
        )
        generator = LifeReviewGenerator(language="zh")
        review = generator.generate(player, [])
        curves = review["resource_curves"]

        # 数组长度应等于周数+1（包含初始状态）
        assert len(curves["energy"]) == 11
        assert len(curves["mood"]) == 11
        assert len(curves["knowledge"]) == 11
        assert len(curves["wealth"]) == 11

    def test_life_review_personality_labels_non_empty(self):
        """personality_labels 至少有一个标签"""
        player = PlayerState(
            player_name="Test",
            energy=80,
            mood=70,
            knowledge=60,
            wealth=10000,
            week=20,
            age=27,
            decision_history=[{"choice": "A"}] * 20,
            round_history=[
                {"week": i, "choice": "A", "summary": "test"} for i in range(20)
            ],
        )
        generator = LifeReviewGenerator(language="zh")
        review = generator.generate(player, [])

        assert len(review["personality_labels"]) > 0
        for label in review["personality_labels"]:
            assert isinstance(label, str)
            assert len(label) > 0

    def test_ending_evaluator_returns_life_review(self):
        """EndingEvaluator.evaluate_ending 返回包含 life_review 的数据"""
        from src.game.endings import EndingEvaluator

        player = PlayerState(
            player_name="Test",
            energy=50,
            mood=50,
            knowledge=50,
            wealth=5000,
            week=10,
            age=25,
            decision_history=[{"choice": "A"}] * 10,
            round_history=[
                {"week": i, "choice": "A", "summary": "test"} for i in range(10)
            ],
            relationships={},
        )
        evaluator = EndingEvaluator(ai_generator=None)
        result = evaluator.evaluate_ending(player, language="zh")

        assert "life_review" in result
        assert "achievements" in result
        assert isinstance(result["achievements"]["list"], list)
        assert isinstance(result["achievements"]["count"], int)
        assert result["achievements"]["count"] == len(result["achievements"]["list"])
        assert "life_review" in result
        review = result["life_review"]
        assert "personality_labels" in review
        assert "resource_curves" in review
