"""Provider-free recovery contracts for final life summaries."""

from typing import Any

from src.game.endings import EndingEvaluator
from src.game.state import PlayerState
import pytest

pytestmark = [pytest.mark.unit]



class _RecordingGenerator:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate_completion(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return "Lin built a careful life through patient choices."


class _FailingGenerator:
    def generate_completion(self, **_kwargs: Any) -> str:
        raise RuntimeError("provider unavailable")


def _state() -> PlayerState:
    return PlayerState(
        player_name="Lin",
        age=34,
        week=72,
        energy=66,
        mood=71,
        knowledge=79,
        wealth=24000,
        character_settings={
            "era": {"year": 1998},
            "age": {"age": 22},
            "gender": {"gender": "nonbinary"},
            "traits": {"personality": "observant"},
        },
        decision_history=[{"choice": "Stayed with the community archive"}],
        four_week_summaries=[{"summary": "Built trust with neighbors."}],
    )


def test_generated_ending_summary_receives_life_context() -> None:
    generator = _RecordingGenerator()

    summary = EndingEvaluator(generator)._generate_summary(_state(), "balanced", "en")

    assert summary == "Lin built a careful life through patient choices."
    assert len(generator.calls) == 1
    prompt = str(generator.calls[0]["prompt"])
    assert "Started at age 22" in prompt
    assert "Stayed with the community archive" in prompt
    assert "Built trust with neighbors." in prompt
    assert generator.calls[0]["max_tokens"] == 4096


def test_failing_ending_summary_generator_returns_localized_template() -> None:
    state = _state()

    summary = EndingEvaluator(_FailingGenerator())._generate_summary(state, "scholar", "zh")

    assert "学术" in summary
    assert str(state.knowledge) in summary
