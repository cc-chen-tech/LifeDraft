"""EndingEvaluator contract tests.

No mocks. Tests pure logic ending evaluation.
"""

from src.game.endings import EndingEvaluator
from src.game.state import PlayerState
import pytest

pytestmark = [pytest.mark.unit]



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
            "relationships": {},
        }
        defaults.update(kwargs)
        return PlayerState(**defaults)

    def test_struggling_ending_low_attributes(self):
        """Very low attributes should yield struggling ending."""
        evaluator = EndingEvaluator()
        state = self._make_state(energy=20, mood=20, knowledge=20)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "struggling"

    def test_average_of_exactly_40_is_balanced(self):
        """The struggling threshold is strictly below 40."""
        evaluator = EndingEvaluator()
        state = self._make_state(energy=40, mood=40, knowledge=40)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "balanced"

    def test_scholar_requires_average_above_60(self):
        evaluator = EndingEvaluator()
        state = self._make_state(energy=40, mood=40, knowledge=85)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "balanced"

    def test_scholar_ending(self):
        """High knowledge should yield scholar ending."""
        evaluator = EndingEvaluator()
        state = self._make_state(energy=70, mood=70, knowledge=85)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "scholar"

    def test_social_ending(self):
        """High relationships should yield social ending."""
        evaluator = EndingEvaluator()
        state = self._make_state(
            energy=70,
            mood=70,
            knowledge=60,
            relationships={"Alice": 80, "Bob": 75, "Charlie": 70},
        )
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "social"

    def test_balanced_ending_default(self):
        """Average stats should yield balanced ending."""
        evaluator = EndingEvaluator()
        state = self._make_state(energy=60, mood=60, knowledge=60)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_type"] == "balanced"

    def test_ending_name_localization_zh(self):
        evaluator = EndingEvaluator()
        state = self._make_state(energy=70, mood=70, knowledge=85)
        result = evaluator.evaluate_ending(state, language="zh")
        assert result["ending_name"] == "学术之路"

    def test_ending_name_localization_en(self):
        evaluator = EndingEvaluator()
        state = self._make_state(energy=70, mood=70, knowledge=85)
        result = evaluator.evaluate_ending(state, language="en")
        assert result["ending_name"] == "Intellectual Pursuit"

    def test_final_stats_present(self):
        evaluator = EndingEvaluator()
        state = self._make_state(energy=55, mood=65, knowledge=75)
        result = evaluator.evaluate_ending(state, language="zh")
        stats = result["final_stats"]
        assert stats["energy"] == 55
        assert stats["mood"] == 65
        assert stats["knowledge"] == 75
        assert set(stats) == {"energy", "mood", "knowledge", "relationships"}

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
        state = self._make_state(energy=20, mood=20, knowledge=20)
        result = evaluator.evaluate_ending(state, language="zh")
        assert "艰难" in result["summary"] or "挑战" in result["summary"]

    def test_template_summary_zh_scholar(self):
        evaluator = EndingEvaluator()
        state = self._make_state(energy=70, mood=70, knowledge=85)
        result = evaluator.evaluate_ending(state, language="zh")
        assert "学术" in result["summary"] or "学识" in result["summary"]

    def test_template_summary_en(self):
        evaluator = EndingEvaluator()
        state = self._make_state(energy=60, mood=60, knowledge=60)
        result = evaluator.evaluate_ending(state, language="en")
        assert "balanced" in result["summary"].lower() or "life" in result["summary"].lower()
