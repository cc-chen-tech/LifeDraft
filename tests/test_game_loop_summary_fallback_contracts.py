from __future__ import annotations

from typing import Any

from src.game.game_loop import GameLoop
from src.game.state import PlayerState


class _PeriodicSummaryProvider:
    def __init__(self):
        self.four_week_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.yearly_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def generate_four_week_summary(self, *args: Any, **kwargs: Any) -> str:
        self.four_week_calls.append((args, kwargs))
        return "Four-week review"

    def generate_yearly_summary(self, *args: Any, **kwargs: Any) -> str:
        self.yearly_calls.append((args, kwargs))
        return "Yearly review"


class _UserSummaryGenerator:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def generate_summary(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"summary_text": "Player review", "decisions_count": len(kwargs["decisions"])}


def _loop(
    language: str = "zh", provider: _PeriodicSummaryProvider | None = None
) -> GameLoop:
    return GameLoop(language=language, ai_generator=provider or _PeriodicSummaryProvider())


def test_fallback_events_preserve_localized_era_round_and_resource_contracts() -> None:
    loop = _loop()
    loop.player_state = PlayerState(
        week=6,
        current_round=1,
        character_settings={"era": {"era_description": "未来城市"}},
    )

    weekly = loop._generate_fallback_event()
    round_event = loop._generate_fallback_event(is_round=True)

    assert "未来城市" in weekly.event_description
    assert [option.effects for option in weekly.options] == [
        {"energy": 5, "mood": 5, "knowledge": 0},
        {"energy": -5, "mood": 0, "knowledge": 5},
    ]
    assert "平静的一天" in round_event.event_description
    assert round_event.options[0].effects["energy"] == 0
    assert round_event.options[0].text == "继续保持现有节奏"


def test_english_fallback_and_progress_work_without_generation() -> None:
    loop = _loop(language="en")

    event = loop._generate_fallback_event()

    assert event.event_description.startswith("You had a quiet week.")
    assert [option.text for option in event.options] == [
        "Keep status quo and move forward",
        "Reflect on life direction",
    ]
    assert loop.get_progress() == {}
    assert loop.is_game_over() is False

    loop.player_state = PlayerState(week=24, age=26)
    progress = loop.get_progress()

    assert loop.get_state() is loop.player_state
    assert progress["week"] == 24
    assert progress["age"] == 26
    assert progress["progress_percent"] > 0


def test_periodic_summaries_store_bounded_history_and_provider_context() -> None:
    provider = _PeriodicSummaryProvider()
    loop = _loop(provider=provider)
    loop.player_state = PlayerState(
        week=48,
        character_settings={"occupation": "architect"},
        story_history=[
            {"week": 3, "story": "outside window"},
            {"week": 4, "story": "first eligible"},
            {"week": 7, "story": "last eligible"},
            {"week": 8, "story": "next period"},
        ],
        decision_history=[
            {"week": 4, "choice": "start"},
            {"week": 7, "choice": "finish"},
            {"week": 8, "choice": "later"},
        ],
        four_week_summaries=[
            {"start_week": 0, "summary": "first block"},
            {"start_week": 4, "summary": "second block"},
            {"start_week": 48, "summary": "future block"},
        ],
    )

    loop._generate_four_week_summary(8)
    loop._generate_yearly_summary(48)

    four_week_args, four_week_kwargs = provider.four_week_calls[0]
    assert four_week_args[0] == ["first eligible", "last eligible"]
    assert [decision["choice"] for decision in four_week_args[1]] == ["start", "finish"]
    assert four_week_args[2:] == (loop.player_state.character_settings, "zh")
    assert four_week_kwargs["game_date_info"] == loop.player_state.get_game_date_info()
    assert loop.player_state.four_week_summaries[-1] == {
        "start_week": 4,
        "end_week": 7,
        "summary": "Four-week review",
        "date_info": loop.player_state.get_game_date_info(),
    }

    yearly_args, yearly_kwargs = provider.yearly_calls[0]
    assert yearly_args[0] == [
        {"start_week": 0, "summary": "first block"},
        {"start_week": 4, "summary": "second block"},
        loop.player_state.four_week_summaries[-1],
    ]
    assert yearly_args[1:] == (loop.player_state.character_settings, 0, 47, "zh")
    assert yearly_kwargs["game_date_info"] == loop.player_state.get_game_date_info()
    assert loop.player_state.yearly_summaries[-1]["summary"] == "Yearly review"
    assert loop.player_state.yearly_summaries[-1]["end_week"] == 47


def test_user_summary_handles_empty_history_and_delegates_bounded_decisions() -> None:
    loop = _loop(language="en")
    loop.player_state = PlayerState(week=7, decision_history=[])

    assert loop.generate_summary(3) == {
        "start_week": 4,
        "end_week": 7,
        "summary": "No decisions made during this period.",
        "highlights": [],
    }

    loop.player_state.decision_history = [
        {"week": 2, "choice": "outside period"},
        {"week": 5, "choice": "inside period"},
        {"week": 7, "choice": "current week"},
    ]
    summary_generator = _UserSummaryGenerator()
    loop.yearly_summary_gen = summary_generator

    result = loop.generate_summary(3)

    assert result == {"summary_text": "Player review", "decisions_count": 2}
    assert summary_generator.calls[0]["start_week"] == 4
    assert summary_generator.calls[0]["end_week"] == 7
    assert [item["choice"] for item in summary_generator.calls[0]["decisions"]] == [
        "inside period",
        "current week",
    ]
    assert summary_generator.calls[0]["end_state"] is loop.player_state
    assert summary_generator.calls[0]["language"] == "en"
