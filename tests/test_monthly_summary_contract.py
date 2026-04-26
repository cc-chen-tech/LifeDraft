"""MonthlySummaryGenerator contract tests.

No mocks. Uses hand-rolled FakeAIClient stub.
"""

from src.game.monthly_summary import MonthlySummaryGenerator
from src.game.state import PlayerState


class FakeAIClient:
    """Stub AI client for testing summary generation."""

    def __init__(self, response="AI generated summary"):
        self.response = response
        self.calls = []

    def generate_completion(
        self, *, prompt, system_prompt, temperature=0.7, max_tokens=4096
    ):
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.response


class TestMonthlySummaryContract:
    """Contract tests for MonthlySummaryGenerator."""

    def _make_state(self, **kwargs):
        defaults = {
            "week": 10,
            "age": 25,
            "current_round": 0,
            "player_name": "TestPlayer",
            "energy": 80,
            "mood": 70,
            "knowledge": 60,
            "wealth": 1000,
        }
        defaults.update(kwargs)
        return PlayerState(**defaults)

    def test_generate_summary_structure(self):
        """Summary should have expected structure."""
        fake = FakeAIClient("Great month!")
        gen = MonthlySummaryGenerator(ai_generator=fake, language="zh")

        previous = {"energy": 70, "mood": 60, "knowledge": 50, "wealth": 500, "age": 24}
        current = self._make_state(
            energy=80, mood=70, knowledge=60, wealth=1000, age=25
        )
        decisions = [{"choice": "Study hard"}]

        result = gen.generate_summary(
            month=1,
            start_week=1,
            end_week=4,
            previous_state=previous,
            current_state=current,
            decisions=decisions,
            language="zh",
        )

        assert result["month"] == 1
        assert result["start_week"] == 1
        assert result["end_week"] == 4
        assert result["age"] == 25
        assert result["summary_text"] == "Great month!"
        assert result["decisions_count"] == 1
        assert "changes" in result
        assert "final_state" in result

    def test_generate_summary_changes_calculated(self):
        """Changes should be calculated from previous to current state."""
        fake = FakeAIClient()
        gen = MonthlySummaryGenerator(ai_generator=fake, language="zh")

        previous = {"energy": 70, "mood": 60, "knowledge": 50, "wealth": 500}
        current = self._make_state(energy=80, mood=70, knowledge=60, wealth=1000)
        decisions = []

        result = gen.generate_summary(
            month=1,
            start_week=1,
            end_week=4,
            previous_state=previous,
            current_state=current,
            decisions=decisions,
            language="zh",
        )

        changes = result["changes"]
        assert changes["energy"] == 10
        assert changes["mood"] == 10
        assert changes["knowledge"] == 10
        assert changes["wealth"] == 500

    def test_generate_summary_no_previous_defaults(self):
        """Missing previous state keys should default to current values (zero change)."""
        fake = FakeAIClient()
        gen = MonthlySummaryGenerator(ai_generator=fake, language="zh")

        previous = {}  # empty
        current = self._make_state(energy=80, mood=70, knowledge=60, wealth=1000)
        decisions = []

        result = gen.generate_summary(
            month=1,
            start_week=1,
            end_week=4,
            previous_state=previous,
            current_state=current,
            decisions=decisions,
            language="zh",
        )

        changes = result["changes"]
        assert changes["energy"] == 0
        assert changes["mood"] == 0
        assert changes["knowledge"] == 0
        assert changes["wealth"] == 0

    def test_generate_summary_ai_error_fallback(self):
        """AI error should trigger fallback summary."""

        class BrokenAIClient:
            def generate_completion(self, **kwargs):
                raise RuntimeError("AI service down")

        gen = MonthlySummaryGenerator(ai_generator=BrokenAIClient(), language="zh")

        previous = {"energy": 70, "mood": 60, "knowledge": 50, "wealth": 500}
        current = self._make_state(energy=80, mood=70, knowledge=60, wealth=1000)
        decisions = []

        result = gen.generate_summary(
            month=2,
            start_week=5,
            end_week=8,
            previous_state=previous,
            current_state=current,
            decisions=decisions,
            language="zh",
        )

        assert result["month"] == 2
        assert "第2个月" in result["summary_text"]
        assert "精力变化" in result["summary_text"]

    def test_generate_summary_english(self):
        """English summary should use English fallback."""

        class BrokenAIClient:
            def generate_completion(self, **kwargs):
                raise RuntimeError("AI down")

        gen = MonthlySummaryGenerator(ai_generator=BrokenAIClient(), language="en")

        previous = {"energy": 70, "mood": 60, "knowledge": 50, "wealth": 500}
        current = self._make_state(energy=80, mood=70, knowledge=60, wealth=1000)
        decisions = []

        result = gen.generate_summary(
            month=1,
            start_week=1,
            end_week=4,
            previous_state=previous,
            current_state=current,
            decisions=decisions,
            language="en",
        )

        assert "Month 1" in result["summary_text"]

    def test_ai_prompt_contains_month_info(self):
        """AI prompt should contain month and week info."""
        fake = FakeAIClient()
        gen = MonthlySummaryGenerator(ai_generator=fake, language="zh")

        previous = {"age": 24}
        current = self._make_state(
            age=25, energy=80, mood=70, knowledge=60, wealth=1000
        )
        decisions = [{"choice": "Work hard"}]

        gen.generate_summary(
            month=3,
            start_week=9,
            end_week=12,
            previous_state=previous,
            current_state=current,
            decisions=decisions,
            language="zh",
        )

        prompt = fake.calls[0]["prompt"]
        assert "第3个月" in prompt
        assert "第9周" in prompt
        assert "第12周" in prompt
        assert "Work hard" in prompt

    def test_ai_prompt_contains_changes(self):
        """AI prompt should contain change info."""
        fake = FakeAIClient()
        gen = MonthlySummaryGenerator(ai_generator=fake, language="zh")

        previous = {"energy": 70, "mood": 60, "knowledge": 50, "wealth": 500}
        current = self._make_state(energy=80, mood=70, knowledge=60, wealth=1000)
        decisions = []

        gen.generate_summary(
            month=1,
            start_week=1,
            end_week=4,
            previous_state=previous,
            current_state=current,
            decisions=decisions,
            language="zh",
        )

        prompt = fake.calls[0]["prompt"]
        assert "精力：+10" in prompt
        assert "财富：+500" in prompt

    def test_final_state_is_dict(self):
        """final_state should be a dict representation of current state."""
        fake = FakeAIClient()
        gen = MonthlySummaryGenerator(ai_generator=fake, language="zh")

        previous = {}
        current = self._make_state(energy=80, mood=70, knowledge=60, wealth=1000)
        decisions = []

        result = gen.generate_summary(
            month=1,
            start_week=1,
            end_week=4,
            previous_state=previous,
            current_state=current,
            decisions=decisions,
            language="zh",
        )

        assert isinstance(result["final_state"], dict)
        assert result["final_state"]["energy"] == 80
