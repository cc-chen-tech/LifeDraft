"""Provider-free contracts for daily narrative transitions."""

import json

from src.ai.models import EventOption
from src.ai.option_generator import OptionGenerator
from src.game.daily_transition import (
    is_valid_daily_transition,
    prepare_daily_option_transitions,
)


def _options() -> list[EventOption]:
    return [
        EventOption(
            text="接受邀请",
            effects={"mood": 2},
            transition_text="这句话落定后，未散的余韵悄然走向明日。",
        ),
        EventOption(text="礼貌拒绝", effects={"energy": 1}),
        EventOption(
            text="再问清细节",
            effects={"knowledge": 2},
            transition_text="情绪+5，明天一定会迎来成功。",
        ),
    ]


def test_daily_transitions_keep_valid_text_and_repair_missing_or_invalid_values() -> (
    None
):
    options = _options()
    state = {
        "timeline": {"version": 2, "day_index": 4},
        "day_history": [],
    }

    prepared = prepare_daily_option_transitions(options, state, language="zh")

    assert prepared[0].transition_text == options[0].transition_text
    assert all(option.transition_text for option in prepared)
    assert len({option.transition_text for option in prepared}) == 3
    assert all(
        is_valid_daily_transition(option.transition_text, language="zh")
        for option in prepared
    )


def test_recent_transition_is_not_reused_after_normalization() -> None:
    duplicate = "这句话落定后 未散的余韵悄然走向明日"
    state = {
        "timeline": {"version": 2, "day_index": 5},
        "day_history": [{"transition_text": duplicate}],
    }

    prepared = prepare_daily_option_transitions(_options(), state, language="zh")

    assert prepared[0].transition_text != _options()[0].transition_text
    assert all(option.transition_text != duplicate for option in prepared)


def test_twelve_recent_fallbacks_still_leave_a_deterministic_unique_transition() -> (
    None
):
    state = {"timeline": {"version": 2, "day_index": 12}, "day_history": []}
    used: list[str] = []

    for day_index in range(13):
        state["timeline"]["day_index"] = day_index
        state["day_history"] = [{"transition_text": text} for text in used[-12:]]
        option = EventOption(text="保持沉默", effects={})
        prepared = prepare_daily_option_transitions([option], state, language="zh")[0]
        assert prepared.transition_text not in used[-12:]
        used.append(str(prepared.transition_text))


def test_legacy_timeline_does_not_invent_transition_text() -> None:
    option = EventOption(text="继续", effects={})

    prepared = prepare_daily_option_transitions(
        [option], {"timeline": {"version": 1}}, language="zh"
    )

    assert prepared[0].transition_text is None


def test_option_generation_parses_and_returns_three_precomputed_daily_transitions() -> (
    None
):
    class Client:
        model = "fixture"

        def call(self, **_kwargs):
            return json.dumps(
                {
                    "options": [
                        {
                            "text": "接受邀请",
                            "effects": {"mood": 2},
                            "transition_text": "话音落下，未散的余韵正悄然走向明日。",
                        },
                        {
                            "text": "礼貌拒绝",
                            "effects": {"energy": 1},
                            "transition_text": "这一刻渐渐安静，明日的光已落在前路。",
                        },
                        {
                            "text": "再问清细节",
                            "effects": {"knowledge": 2},
                            "transition_text": "今日的回声渐远，明日已从静处缓缓靠近。",
                        },
                    ]
                },
                ensure_ascii=False,
            )

    event = OptionGenerator(Client()).generate_options_only(
        "故事停在一项需要回应的邀请前。",
        {
            "timeline": {"version": 2, "day_index": 0},
            "day_history": [],
        },
        language="zh",
        retry_count=1,
    )

    assert len(event.options) == 3
    assert [option.transition_text for option in event.options] == [
        "话音落下，未散的余韵正悄然走向明日。",
        "这一刻渐渐安静，明日的光已落在前路。",
        "今日的回声渐远，明日已从静处缓缓靠近。",
    ]
