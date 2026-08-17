"""Regression tests for restoring a saved current event."""

import time
from types import SimpleNamespace

from src.ai.models import EventOption
from src.ai.models import GameEvent
from src.game.game_loop import GameLoop
from src.game.round.event_generator import RoundEventGenerator
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.slow]



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


def test_resume_existing_story_uses_fallback_options_when_options_generation_times_out() -> None:
    """A slow options-only AI call must not leave a recovered story without choices."""

    class SlowOptionsAI:
        def generate_options_only(self, **_kwargs):
            time.sleep(0.2)
            return GameEvent(
                event_description="too late",
                options=[EventOption(text="迟到选项", effects={})],
            )

    player_state = SimpleNamespace(
        week=0,
        current_round=1,
        round_history=[],
        last_round_full_story="",
        current_event_data={"event_description": "already saved", "options": []},
        character_settings={},
        to_dict=lambda: {"week": 0, "current_round": 1},
    )
    session = SimpleNamespace(
        get_cached_options=lambda *_args: None,
        set_cached_options=lambda *_args: None,
    )
    generator = RoundEventGenerator(
        player_state_getter=lambda: player_state,
        ai_generator=SlowOptionsAI(),
        language_getter=lambda: "zh",
        character_introduction_service=None,
        summary_selector=None,
        relationship_service=None,
    )
    generator._OPTIONS_ONLY_TIMEOUT = 0.01
    existing_story = (
        "林见微已经追到科技公司地下机房，正在等待下一步选项。"
        "她把刚刚发生的变化、同伴的提醒和下一步风险全部记在本子上。"
        "走廊尽头的备用电源还在闪烁，陆昊然刚发来消息提醒她先确认服务器日志，"
        "陈晓雨则建议她不要独自进入机房深处。她停在门口，意识到下一步选择会影响"
        "团队对她判断力的信任，也会决定这条线索能否继续追下去。"
    )
    generator.current_event = SimpleNamespace(
        event_description=existing_story,
        options=[],
    )

    event = generator.generate_round_event(session=session)

    assert event is not None
    assert event.event_description.startswith("林见微已经追到科技公司地下机房")
    assert len(event.options) == 3
    assert event.options[0].text != "迟到选项"
    assert player_state.current_event_data == event.model_dump()


def test_resume_existing_story_reads_legacy_four_option_cache_without_normalizing() -> None:
    """Cached old saves remain readable with their original two-to-four option shape."""

    existing_story = (
        "林见微已经追到科技公司地下机房，正在等待下一步选项。"
        "她把刚刚发生的变化、同伴的提醒和下一步风险全部记在本子上。"
        "走廊尽头的备用电源还在闪烁，陆昊然刚发来消息提醒她先确认服务器日志，"
        "陈晓雨则建议她不要独自进入机房深处。她停在门口，意识到下一步选择会影响"
        "团队对她判断力的信任，也会决定这条线索能否继续追下去。"
    )
    cached_options = [
        EventOption(text=f"旧存档行动{index}", effects={"knowledge": index}).model_dump()
        for index in range(4)
    ]
    player_state = SimpleNamespace(
        week=0,
        current_round=1,
        round_history=[],
        last_round_full_story="",
        current_event_data={"event_description": existing_story, "options": []},
        character_settings={},
        to_dict=lambda: {"week": 0, "current_round": 1},
    )
    session = SimpleNamespace(
        get_cached_options=lambda *_args: cached_options,
        set_cached_options=lambda *_args: None,
    )
    generator = RoundEventGenerator(
        player_state_getter=lambda: player_state,
        ai_generator=SimpleNamespace(),
        language_getter=lambda: "zh",
        character_introduction_service=None,
        summary_selector=None,
        relationship_service=None,
    )
    generator.current_event = SimpleNamespace(
        event_description=existing_story,
        options=[],
    )

    event = generator.generate_round_event(session=session)

    assert event is not None
    assert event.event_description == existing_story
    assert [option.text for option in event.options] == [
        "旧存档行动0",
        "旧存档行动1",
        "旧存档行动2",
        "旧存档行动3",
    ]
