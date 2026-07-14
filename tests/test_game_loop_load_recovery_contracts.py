"""Provider-free GameLoop saved-event recovery contracts."""

from types import SimpleNamespace

from src.game.game_loop import GameLoop


def _loop() -> GameLoop:
    return GameLoop(ai_generator=SimpleNamespace())


def _event_data(options: list[dict[str, object]]) -> dict[str, object]:
    return {"event_description": "Saved event.", "options": options}


def test_load_game_restores_valid_saved_current_event() -> None:
    loop = _loop()

    state = loop.load_game(
        {
            "player_name": "Lin",
            "week": 2,
            "current_round": 1,
            "current_event_data": _event_data(
                [{"text": "Continue", "effects": {}}, {"text": "Wait", "effects": {}}]
            ),
            "round_history": [],
            "decision_history": [],
            "yearly_summaries": [],
        }
    )

    assert loop.current_event is not None
    assert loop.current_event.event_description == "Saved event."
    assert state.current_event_data is not None
    assert loop.last_event_week == 2


def test_load_game_clears_stale_current_event_already_in_history() -> None:
    loop = _loop()

    state = loop.load_game(
        {
            "player_name": "Lin",
            "week": 2,
            "current_round": 1,
            "current_event_data": _event_data(
                [{"text": "Continue", "effects": {}}, {"text": "Wait", "effects": {}}]
            ),
            "round_history": [{"week": 2, "round": 1, "event_description": "Saved event."}],
            "decision_history": [],
            "yearly_summaries": [],
        }
    )

    assert state.current_event_data is None
    assert loop.current_event is None
    assert loop.last_event_week == 1


def test_load_game_recovers_partial_event_when_saved_options_are_invalid() -> None:
    loop = _loop()

    loop.load_game(
        {
            "player_name": "Lin",
            "week": 2,
            "current_round": 1,
            "current_event_data": _event_data([{"text": "Only option", "effects": {}}]),
            "round_history": [],
            "decision_history": [],
            "yearly_summaries": [],
        }
    )

    assert loop.current_event is not None
    assert loop.current_event.event_description == "Saved event."
    assert [option.text for option in loop.current_event.options] == ["Only option"]
