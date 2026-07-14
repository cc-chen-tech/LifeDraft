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


def test_load_game_without_saved_event_allows_current_week_generation() -> None:
    loop = _loop()

    loop.load_game(
        {
            "player_name": "Lin",
            "week": 4,
            "current_round": 0,
            "current_event_data": None,
            "round_history": [],
            "decision_history": [],
            "yearly_summaries": [],
        }
    )

    assert loop.current_event is None
    assert loop.last_event_week == 3
    assert loop.last_year_start_week == 0


def test_load_game_restores_year_boundary_from_latest_summary() -> None:
    loop = _loop()

    loop.load_game(
        {
            "player_name": "Lin",
            "week": 54,
            "current_round": 0,
            "current_event_data": None,
            "round_history": [],
            "decision_history": [{"week": 54}],
            "yearly_summaries": [{"end_week": 51, "summary": "Year one."}],
        }
    )

    assert loop.last_year_start_week == 52
    assert loop.last_event_week == 54


def test_start_new_game_resets_event_tracking_for_default_state() -> None:
    loop = _loop()
    loop.current_event = object()  # type: ignore[assignment]
    loop.last_event_week = 99

    state = loop.start_new_game()

    assert state.current_event_data is None
    assert loop.current_event is None
    assert loop.last_event_week == -1


def test_start_new_game_uses_supplied_state_and_clears_saved_event() -> None:
    loop = _loop()

    state = loop.start_new_game(
        {
            "player_name": "Lin",
            "week": 5,
            "current_round": 2,
            "current_event_data": _event_data(
                [{"text": "Continue", "effects": {}}, {"text": "Wait", "effects": {}}]
            ),
        }
    )

    assert state.player_name == "Lin"
    assert state.week == 5
    assert state.current_event_data is None


def test_start_new_game_initializes_characters_from_relationship_settings() -> None:
    state = _loop().start_new_game(
        {
            "player_name": "Lin",
            "character_settings": {
                "relationships": {
                    "key_people": [{"name": "Wei", "role": "friend", "relationship": "ally"}]
                }
            },
        }
    )

    assert "Wei" in state.characters
