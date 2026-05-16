"""EndingEvaluator contract tests.

No mocks. Tests pure logic ending evaluation.
"""

from src.game.endings import EndingEvaluator
from src.game.state import PlayerState


class TestEndingEvaluatorContract:
    """Contract tests for ending evaluation."""

    def _make_state(self, **kwargs):
        defaults = {
            "week": 100,
            "age": 30,
            "current_round": 0,
            "player_name": "Test",
            "energy": 50,
            "mood": 50,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
        }
        defaults.update(kwargs)
        return PlayerState(**defaults)

    def test_struggling_ending_low_attributes(self):
        """Very low attributes should yield struggling ending."""
        evaluator = EndingEvaluator()
        state = self._make_state(energy=20, mood=20, knowledge=20, wealth=1000)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "struggling"

    def test_struggling_ending_low_wealth_and_avg(self):
        """Low wealth with moderately low attributes should yield struggling."""
        evaluator = EndingEvaluator()
        state = self._make_state(energy=45, mood=45, knowledge=45, wealth=3000)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "struggling"

    def test_wealthy_ending(self):
        """High wealth should yield wealthy ending."""
        evaluator = EndingEvaluator()
        state = self._make_state(energy=60, mood=60, knowledge=60, wealth=80000)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "wealthy"

    def test_scholar_ending(self):
        """High knowledge should yield scholar ending."""
        evaluator = EndingEvaluator()
        state = self._make_state(energy=70, mood=70, knowledge=85, wealth=10000)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "scholar"

    def test_social_ending(self):
        """High relationships should yield social ending."""
        evaluator = EndingEvaluator()
        state = self._make_state(
            energy=70,
            mood=70,
            knowledge=60,
            wealth=10000,
            relationships={"Alice": 80, "Bob": 75, "Charlie": 70},
        )
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "social"

    def test_balanced_ending_default(self):
        """Average stats should yield balanced ending."""
        evaluator = EndingEvaluator()
        state = self._make_state(energy=60, mood=60, knowledge=60, wealth=20000)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "balanced"

    def test_ending_name_localization_zh(self):
        evaluator = EndingEvaluator()
        state = self._make_state(wealth=80000, energy=60, mood=60, knowledge=60)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_name"] == "财富自由"

    def test_ending_name_localization_en(self):
        evaluator = EndingEvaluator()
        state = self._make_state(wealth=80000, energy=60, mood=60, knowledge=60)
        result = evaluator.evaluate_ending(state, language="en")
        assert result["ending_name"] == "Wealthy Success"

    def test_final_stats_present(self):
        evaluator = EndingEvaluator()
        state = self._make_state(energy=55, mood=65, knowledge=75, wealth=15000)
        result = evaluator.evaluate_ending(state, language="zh")
        stats = result["final_stats"]
        assert stats["energy"] == 55
        assert stats["mood"] == 65
        assert stats["knowledge"] == 75
        assert stats["wealth"] == 15000

    def test_achievements_present(self):
        evaluator = EndingEvaluator()
        state = self._make_state()
        result = evaluator.evaluate_ending(state, language="zh")
        assert "achievements" in result
        assert "list" in result["achievements"]
        assert "count" in result["achievements"]

    def test_life_review_present(self):
        evaluator = EndingEvaluator()
        state = self._make_state()
        result = evaluator.evaluate_ending(state, language="zh")
        assert "life_review" in result
        assert isinstance(result["life_review"], dict)

    def test_template_summary_zh_struggling(self):
        evaluator = EndingEvaluator()
        state = self._make_state(energy=20, mood=20, knowledge=20, wealth=1000)
        result = evaluator.evaluate_ending(state, language="zh")
        assert "艰难" in result["summary"] or "挑战" in result["summary"]

    def test_template_summary_zh_wealthy(self):
        evaluator = EndingEvaluator()
        state = self._make_state(energy=60, mood=60, knowledge=60, wealth=60000)
        result = evaluator.evaluate_ending(state, language="zh")
        assert "财富" in result["summary"]

    def test_template_summary_zh_scholar(self):
        evaluator = EndingEvaluator()
        state = self._make_state(energy=70, mood=70, knowledge=85, wealth=10000)
        result = evaluator.evaluate_ending(state, language="zh")
        assert "学术" in result["summary"] or "学识" in result["summary"]

    def test_template_summary_en(self):
        evaluator = EndingEvaluator()
        state = self._make_state(energy=60, mood=60, knowledge=60, wealth=20000)
        result = evaluator.evaluate_ending(state, language="en")
        assert "balanced" in result["summary"].lower() or "life" in result["summary"].lower()
