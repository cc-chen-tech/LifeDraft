from src.game.game_loop import GameLoop
from src.game.state import PlayerState
import pytest

pytestmark = [pytest.mark.unit]



def _loop_with_state(**updates: int) -> GameLoop:
    loop = GameLoop(language="zh")
    loop.player_state = PlayerState(week=1, energy=80, mood=80)
    loop.current_event = None
    for key, value in updates.items():
        setattr(loop.player_state, key, value)
    return loop


def test_weekly_decay_applies_only_below_low_resource_threshold() -> None:
    loop = _loop_with_state(energy=29, mood=30)

    loop._apply_weekly_decay()

    assert loop.player_state is not None
    assert loop.player_state.energy < 29
    assert loop.player_state.mood == 30


def test_week_advance_clears_persisted_event_without_triggering_summaries() -> None:
    loop = _loop_with_state()
    assert loop.player_state is not None
    loop.player_state.current_event_data = {"event_description": "已展示的故事", "options": []}

    continues = loop.advance_to_next_week()

    assert continues is True
    assert loop.player_state.week == 2
    assert loop.current_event is None
    assert loop.player_state.current_event_data is None
