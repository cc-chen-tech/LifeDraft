from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from src.game.round.finalizer import RoundFinalizer
from src.game.state import PlayerState
import pytest

pytestmark = [pytest.mark.unit]



class _SummaryGenerator:
    def __init__(self, result: dict[str, Any] | None = None, fails: bool = False):
        self.result = result or {"summary": "generated", "bonus_effects": {}}
        self.fails = fails
        self.calls: list[dict[str, Any]] = []

    def generate_weekly_summary(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.fails:
            raise RuntimeError("summary unavailable")
        return self.result


class _StoryCompressor:
    def __init__(self):
        self.args: tuple[Any, ...] | None = None

    def compress_story(self, *args: Any) -> dict[str, Any]:
        self.args = args
        return {"summary": "compressed"}


class _CharacterCompleter:
    def __init__(self):
        self.checked: list[Any] = []
        self.family_args: tuple[Any, ...] | None = None

    def check_and_fix_missing_attributes(self, player_state: Any) -> None:
        self.checked.append(player_state)

    def generate_family_members_details(self, *args: Any) -> list[dict[str, str]]:
        self.family_args = args
        return [{"name": "Avery"}]


def _finalizer(
    player_state: Any,
    *,
    language: str = "zh",
    summary_generator: _SummaryGenerator | None = None,
    story_compressor: _StoryCompressor | None = None,
    character_completer: _CharacterCompleter | None = None,
) -> RoundFinalizer:
    return RoundFinalizer(
        player_state_getter=lambda: player_state,
        ai_generator=summary_generator or _SummaryGenerator(),
        language_getter=lambda: language,
        story_service=story_compressor or _StoryCompressor(),
        character_creator=character_completer or _CharacterCompleter(),
    )


def test_weekly_summary_empty_rounds_uses_localized_fallback_and_checks_attributes() -> None:
    player = PlayerState(week=2)
    completer = _CharacterCompleter()
    finalizer = _finalizer(player, language="en", character_completer=completer)

    result = finalizer.generate_weekly_summary()

    assert result == {"summary": "This week passed quietly.", "bonus_effects": {}}
    assert completer.checked == [player]


def test_weekly_summary_delegates_context_and_recovers_from_generator_failure() -> None:
    player = PlayerState(week=3, character_settings={"role": "artist"})
    player.round_history.append({"week": 3, "story": "A studio opened."})
    generator = _SummaryGenerator(fails=True)
    finalizer = _finalizer(player, language="zh", summary_generator=generator)

    result = finalizer.generate_weekly_summary()

    assert result == {"summary": "本周充实而忙碌。", "bonus_effects": {}}
    assert generator.calls[0]["rounds"] == player.get_current_week_rounds()
    assert "wealth_context" not in generator.calls[0]


def test_compression_round_information_and_weekly_decay_use_current_state() -> None:
    player = PlayerState(
        player_name="Alex River",
        week=4,
        current_round=2,
        rounds_per_week=3,
        mood=40,
        character_settings={"family": "configured"},
    )
    player.pending_storylines = ["opening"]
    player.established_facts = ["fact"]
    player.character_habits = ["habit"]
    player.round_history.extend(
        [
            {"week": 4, "story": "first"},
            {"week": 4, "story": "second"},
        ]
    )
    compressor = _StoryCompressor()
    completer = _CharacterCompleter()
    finalizer = _finalizer(
        player,
        story_compressor=compressor,
        character_completer=completer,
    )

    assert finalizer.compress_round_story("story", "choice") == {"summary": "compressed"}
    assert compressor.args == ("story", "choice", ["opening"], ["fact"], ["habit"])
    assert finalizer.get_round_info() == {
        "week": 4,
        "current_round": 2,
        "rounds_per_week": 3,
        "round_name": player.get_round_name("zh"),
        "is_last_round": True,
        "week_rounds_completed": 2,
    }

    finalizer._apply_weekly_decay()
    assert player.mood == 38
    assert finalizer._generate_family_members_details(["Avery"]) == [{"name": "Avery"}]
    assert completer.family_args == (["Avery"], player.character_settings, "Alex River")


def test_periodic_summaries_require_sufficient_history_and_append_records() -> None:
    player = SimpleNamespace(
        weekly_summaries=[{"week": index, "summary": f"Week {index}"} for index in range(4)],
        four_week_summaries=[{"week": index * 4} for index in range(12)],
        yearly_summaries=[],
    )
    finalizer = _finalizer(player)

    finalizer._generate_four_week_summary(4)
    finalizer._generate_yearly_summary(48)

    assert player.four_week_summaries[-1]["week"] == 4
    assert "Week 3: Week 3" in player.four_week_summaries[-1]["combined_summary"]
    assert player.yearly_summaries == [
        {"week": 48, "year": 1, "summaries": player.four_week_summaries[-12:]}
    ]


def test_finalizer_handles_absent_player_state_without_side_effects() -> None:
    finalizer = _finalizer(None)

    assert finalizer.generate_weekly_summary() == {"summary": "", "bonus_effects": {}}
    assert finalizer.get_round_info() == {}
    assert finalizer._generate_family_members_details(["Avery"]) == []
