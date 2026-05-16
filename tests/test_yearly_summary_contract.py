"""YearlySummaryGenerator contract tests.

No mocks. Uses hand-rolled FakeAIClient stub.
"""

from src.game.state import PlayerState
from src.game.yearly_summary import YearlySummaryGenerator


class FakeAIClient:
    """Stub AI client for testing summary generation."""

    def __init__(self, response="AI generated yearly summary"):
        self.response = response
        self.calls = []

    def generate_completion(
        self, *, prompt, system_prompt, temperature=0.8, max_tokens=4096
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


class TestYearlySummaryContract:
    """Contract tests for YearlySummaryGenerator."""

    def _make_state(self, **kwargs):
        defaults = {
            "week": 50,
            "age": 26,
            "current_round": 0,
            "player_name": "TestPlayer",
            "energy": 80,
            "mood": 70,
            "knowledge": 60,
            "wealth": 10000,
        }
        defaults.update(kwargs)
        return PlayerState(**defaults)

    def test_generate_summary_structure(self):
        fake = FakeAIClient("Great year!")
        gen = YearlySummaryGenerator(ai_generator=fake, language="zh")

        start = {"energy": 70, "mood": 60, "knowledge": 50, "wealth": 5000, "age": 25}
        end = self._make_state(energy=80, mood=70, knowledge=60, wealth=10000, age=26)
        monthly = [{"summary_text": "Month 1 was good"}]
        decisions = [{"choice": "Study"}]

        result = gen.generate_summary(
            year=1,
            start_week=1,
            end_week=48,
            start_state=start,
            end_state=end,
            monthly_summaries=monthly,
            decisions=decisions,
            language="zh",
        )

        assert result["year"] == 1
        assert result["start_week"] == 1
        assert result["end_week"] == 48
        assert result["age"] == 26
        assert result["summary_text"] == "Great year!"
        assert result["decisions_count"] == 1
        assert "changes" in result
        assert "final_state" in result

    def test_generate_summary_changes(self):
        fake = FakeAIClient()
        gen = YearlySummaryGenerator(ai_generator=fake, language="zh")

        start = {"energy": 70, "mood": 60, "knowledge": 50, "wealth": 5000, "age": 25}
        end = self._make_state(energy=80, mood=70, knowledge=60, wealth=10000, age=26)

        result = gen.generate_summary(
            year=1,
            start_week=1,
            end_week=48,
            start_state=start,
            end_state=end,
            monthly_summaries=[],
            decisions=[],
            language="zh",
        )

        changes = result["changes"]
        assert changes["energy"] == 10
        assert changes["mood"] == 10
        assert changes["knowledge"] == 10
        assert changes["wealth"] == 5000
        assert changes["age"] == 1

    def test_generate_summary_no_previous_defaults(self):
        fake = FakeAIClient()
        gen = YearlySummaryGenerator(ai_generator=fake, language="zh")

        start = {}
        end = self._make_state(energy=80, mood=70, knowledge=60, wealth=10000, age=26)

        result = gen.generate_summary(
            year=1,
            start_week=1,
            end_week=48,
            start_state=start,
            end_state=end,
            monthly_summaries=[],
            decisions=[],
            language="zh",
        )

        changes = result["changes"]
        assert changes["energy"] == 0
        assert changes["age"] == 0

    def test_generate_summary_ai_error_fallback(self):
        class BrokenAIClient:
            def generate_completion(self, **kwargs):
                raise RuntimeError("AI down")

        gen = YearlySummaryGenerator(ai_generator=BrokenAIClient(), language="zh")

        start = {"energy": 70, "mood": 60, "knowledge": 50, "wealth": 5000, "age": 25}
        end = self._make_state(energy=80, mood=70, knowledge=60, wealth=10000, age=26)

        result = gen.generate_summary(
            year=2,
            start_week=49,
            end_week=96,
            start_state=start,
            end_state=end,
            monthly_summaries=[],
            decisions=[],
            language="zh",
        )

        assert result["year"] == 2
        assert "第2年" in result["summary_text"]
        assert "精力变化" in result["summary_text"]

    def test_generate_summary_english(self):
        class BrokenAIClient:
            def generate_completion(self, **kwargs):
                raise RuntimeError("AI down")

        gen = YearlySummaryGenerator(ai_generator=BrokenAIClient(), language="en")

        start = {}
        end = self._make_state(energy=80, mood=70, knowledge=60, wealth=10000, age=26)

        result = gen.generate_summary(
            year=1,
            start_week=1,
            end_week=48,
            start_state=start,
            end_state=end,
            monthly_summaries=[],
            decisions=[],
            language="en",
        )

        assert "Year 1" in result["summary_text"]

    def test_prompt_contains_year_info(self):
        fake = FakeAIClient()
        gen = YearlySummaryGenerator(ai_generator=fake, language="zh")

        start = {"age": 25}
        end = self._make_state(age=26, energy=80, mood=70, knowledge=60, wealth=10000)
        monthly = [{"summary_text": "Good month"}]
        decisions = [{"choice": "Work hard"}]

        gen.generate_summary(
            year=1,
            start_week=1,
            end_week=48,
            start_state=start,
            end_state=end,
            monthly_summaries=monthly,
            decisions=decisions,
            language="zh",
        )

        prompt = fake.calls[0]["prompt"]
        assert "第1年" in prompt
        assert "Work hard" in prompt
        assert "Good month" in prompt

    def test_prompt_contains_monthly_highlights_sampling(self):
        fake = FakeAIClient()
        gen = YearlySummaryGenerator(ai_generator=fake, language="zh")

        start = {"age": 25}
        end = self._make_state(age=26)
        monthly = [{"summary_text": f"Month {i}"} for i in range(12)]

        gen.generate_summary(
            year=1,
            start_week=1,
            end_week=48,
            start_state=start,
            end_state=end,
            monthly_summaries=monthly,
            decisions=[],
            language="zh",
        )

        prompt = fake.calls[0]["prompt"]
        # Should sample from 12 monthly summaries
        assert "Month" in prompt

    def test_final_state_is_dict(self):
        fake = FakeAIClient()
        gen = YearlySummaryGenerator(ai_generator=fake, language="zh")

        start = {}
        end = self._make_state(energy=80, mood=70, knowledge=60, wealth=10000)

        result = gen.generate_summary(
            year=1,
            start_week=1,
            end_week=48,
            start_state=start,
            end_state=end,
            monthly_summaries=[],
            decisions=[],
            language="zh",
        )

        assert isinstance(result["final_state"], dict)
        assert result["final_state"]["energy"] == 80
