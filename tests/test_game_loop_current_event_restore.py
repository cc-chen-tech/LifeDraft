"""Regression tests for restoring a saved current event."""

from src.ai.models import EventOption
from src.game.game_loop import GameLoop


def test_loaded_current_event_survives_round_service_initialization() -> None:
    """Refresh recovery must not regenerate when a saved current_event_data exists."""

    loop = GameLoop(language="zh")
    loop.load_game(
        {
            "age": 25,
            "week": 0,
            "current_round": 0,
            "current_event_data": {
                "event_description": "林见微已经看到的当前故事正文。",
                "options": [
                    EventOption(text="继续查证", effects={}).model_dump(),
                    EventOption(text="暂缓一步", effects={}).model_dump(),
                ],
            },
            "round_history": [],
        }
    )

    assert loop.current_event is not None

    loop._init_round_services()

    assert loop.current_event is not None
    assert loop.current_event.event_description == "林见微已经看到的当前故事正文。"
    assert [option.text for option in loop.current_event.options] == ["继续查证", "暂缓一步"]


def test_loaded_partial_current_event_preserves_story_while_options_are_pending() -> None:
    """A refresh during option generation must keep the persisted story visible."""

    loop = GameLoop(language="zh")
    loop.load_game(
        {
            "age": 25,
            "week": 2,
            "current_round": 2,
            "current_event_data": {
                "event_description": "林见微已经追到科技公司地下机房，正在等待下一步选项。",
                "options": [],
            },
            "round_history": [],
        }
    )

    assert loop.current_event is not None
    assert loop.current_event.event_description == "林见微已经追到科技公司地下机房，正在等待下一步选项。"
    assert loop.current_event.options == []


def test_loaded_partial_current_event_drops_malformed_legacy_options() -> None:
    """Malformed saved options must not prevent recovering the persisted story."""

    loop = GameLoop(language="zh")
    loop.load_game(
        {
            "age": 25,
            "week": 2,
            "current_round": 2,
            "current_event_data": {
                "event_description": "林见微已经追到科技公司地下机房，正在等待下一步选项。",
                "options": [{"text": "缺少 effects 的旧数据"}],
            },
            "round_history": [],
        }
    )

    assert loop.current_event is not None
    assert loop.current_event.event_description == "林见微已经追到科技公司地下机房，正在等待下一步选项。"
    assert loop.current_event.options == []
