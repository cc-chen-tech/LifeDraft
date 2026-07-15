from __future__ import annotations

from typing import Any

from src.game.round.finalizer import RoundFinalizer
from src.game.state import PlayerState


class _WeeklySummaryProvider:
    def __init__(self, result: dict[str, Any]):
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def generate_weekly_summary(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.result


class _CharacterCompleter:
    def __init__(self):
        self.checked: list[PlayerState] = []

    def check_and_fix_missing_attributes(self, player_state: PlayerState) -> None:
        self.checked.append(player_state)


class _SynchronousFinalizer(RoundFinalizer):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.enrichment_weeks: list[int] = []

    def _start_post_week_enrichment(self, new_week: int) -> None:
        self.enrichment_weeks.append(new_week)


def _state(*, week: int = 0, wealth: int = 100) -> PlayerState:
    state = PlayerState(
        player_name="Lin",
        week=week,
        current_round=2,
        rounds_per_week=3,
        energy=50,
        mood=60,
        knowledge=70,
        wealth=wealth,
        character_settings={"occupation": "architect"},
    )
    state.round_history.append(
        {"week": week, "round": 2, "summary": "Completed a client review."}
    )
    return state


def _finalizer(
    state: PlayerState,
    provider: _WeeklySummaryProvider,
    completer: _CharacterCompleter,
) -> _SynchronousFinalizer:
    return _SynchronousFinalizer(
        player_state_getter=lambda: state,
        ai_generator=provider,
        language_getter=lambda: "en",
        story_service=object(),
        character_creator=completer,
    )


def test_finalization_records_wealth_bonus_summary_and_week_transition() -> None:
    state = _state(wealth=100)
    provider = _WeeklySummaryProvider(
        {
            "summary": "The client review closed the week.",
            "bonus_effects": {"energy": 3, "mood": 4, "knowledge": 2, "wealth": 25},
        }
    )
    completer = _CharacterCompleter()
    finalizer = _finalizer(state, provider, completer)
    result: dict[str, Any] = {}
    statuses: list[str] = []
    expected_date_info = state.get_game_date_info()

    finalizer.finalize_week(result, status_callback=statuses.append)

    assert statuses == ["weekly_summary"]
    assert completer.checked == [state]
    assert provider.calls[0]["rounds"] == state.round_history
    assert provider.calls[0]["wealth_context"]["current_balance"] == 100
    assert result == {
        "weekly_summary": "The client review closed the week.",
        "bonus_effects": {"energy": 3, "mood": 4, "knowledge": 2, "wealth": 25},
    }
    assert state.wealth == 125
    transaction = state.wealth_ledger["transactions"][-1]
    assert transaction["transaction_id"] == "weekly-bonus:w0"
    assert transaction["requested_delta"] == 25
    assert transaction["closing_balance"] == 125
    assert (state.energy, state.mood, state.knowledge) == (53, 62, 72)
    assert state.week == 1
    assert state.current_round == 0
    assert finalizer.enrichment_weeks == [1]
    assert state.weekly_summaries == [
        {
            "week": 0,
            "summary": "The client review closed the week.",
            "bonus_effects": {"energy": 3, "mood": 4, "knowledge": 2, "wealth": 25},
            "date_info": expected_date_info,
        }
    ]


def test_finalization_without_wealth_bonus_persists_ledger_and_resources() -> None:
    state = _state(wealth=210)
    provider = _WeeklySummaryProvider(
        {"summary": "A quiet week.", "bonus_effects": {"energy": -2, "mood": 1}}
    )
    finalizer = _finalizer(state, provider, _CharacterCompleter())
    result: dict[str, Any] = {}

    finalizer.finalize_week(result)

    assert state.wealth == 210
    assert state.wealth_ledger["opening_balance"] == 210
    assert state.wealth_ledger["balance_snapshot"] == 210
    assert (state.energy, state.mood, state.knowledge) == (48, 59, 70)
    assert result["bonus_effects"] == {"energy": -2, "mood": 1}


def test_periodic_summary_records_require_and_preserve_complete_history() -> None:
    state = _state(week=48)
    state.weekly_summaries = [
        {"week": week, "summary": f"Week {week}"} for week in range(4)
    ]
    state.four_week_summaries = [
        {"week": week * 4, "combined_summary": f"Block {week}"}
        for week in range(12)
    ]
    finalizer = _finalizer(
        state,
        _WeeklySummaryProvider({"summary": "unused", "bonus_effects": {}}),
        _CharacterCompleter(),
    )

    finalizer._generate_four_week_summary(4)
    finalizer._generate_yearly_summary(48)

    four_week_record = state.four_week_summaries[-1]
    assert four_week_record["week"] == 4
    assert four_week_record["summaries"] == state.weekly_summaries
    assert "Week 3: Week 3" in four_week_record["combined_summary"]
    assert state.yearly_summaries[-1] == {
        "week": 48,
        "year": 1,
        "summaries": state.four_week_summaries[-12:],
    }
