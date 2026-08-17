"""Contracts for localized option display budgets and item-level repair."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from src.ai.budgets import (
    GenerationCallTracker,
    measure_option_length,
    resolve_display_budget,
    resolve_narrative_budget,
)
from src.ai.models import EventOption, GameEvent
from src.ai.generator import EventGenerator
from src.ai.option_generator import OptionGenerator
from src.game.round.event_generator import RoundEventGenerator

pytestmark = [pytest.mark.unit]



class SequenceClient:
    model = "test-model"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def call(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self.responses.pop(0)


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("zh", (3, 8, 24, 40, 2, 2, "characters")),
        ("en", (3, 3, 12, 16, 2, 2, "words")),
    ],
)
def test_display_budget_defaults_are_localized(
    language: str, expected: tuple[int, int, int, int, int, int, str]
) -> None:
    budget = resolve_display_budget(language, option_call_limit=2)

    assert (
        budget.option_count,
        budget.target_min,
        budget.target_max,
        budget.repair_threshold,
        budget.option_call_limit,
        budget.max_display_lines,
        budget.unit,
    ) == expected
    assert resolve_display_budget(language, option_call_limit=99).option_call_limit == 2


def test_option_measurement_uses_unicode_characters_and_english_words() -> None:
    assert measure_option_length("先 问清楚。", "zh") == 5
    assert measure_option_length("Ask a trusted ally to cross-check", "en") == 6


def test_option_prompts_request_exactly_three_with_localized_targets() -> None:
    from config.prompts.story_prompts import (
        get_event_generation_prompt,
        get_options_only_prompt,
    )
    from src.game.round.event_generator import RoundEventGenerator

    zh = get_options_only_prompt("故事", {}, language="zh")
    en = get_options_only_prompt("Story", {}, language="en")
    player_state = {
        "age": 25,
        "energy": 70,
        "mood": 60,
        "knowledge": 50,
        "relationships": {},
        "decision_history": [],
    }
    zh_event = get_event_generation_prompt(player_state, language="zh")
    en_event = get_event_generation_prompt(player_state, language="en")
    generator = RoundEventGenerator(
        player_state_getter=lambda: None,
        ai_generator=None,
        language_getter=lambda: "zh",
        character_introduction_service=None,
        summary_selector=None,
        relationship_service=None,
    )
    scheduled_state = {
        "player_name": "林岚",
        "week": 2,
        "current_round": 1,
        "rounds_per_week": 3,
    }
    scheduled = [{"description": "兑现承诺", "parties": ["林岚"]}]
    zh_scheduled = generator._build_scheduled_event_prompt(
        scheduled, scheduled_state, {}, "zh"
    )
    en_scheduled = generator._build_scheduled_event_prompt(
        scheduled, scheduled_state, {}, "en"
    )

    for prompt in (zh, zh_event, zh_scheduled):
        assert "恰好3个" in prompt
        assert "8-24字" in prompt
        assert "2-4" not in prompt and "3-4" not in prompt
        assert "最多15字" not in prompt
    for prompt in (en, en_event, en_scheduled):
        assert "exactly 3 options" in prompt
        assert "3-12 words" in prompt
        assert "2-4" not in prompt and "3-4" not in prompt
        assert "max 15 words" not in prompt and "max 15 chars" not in prompt


def _payload(options: list[dict[str, Any]]) -> str:
    return json.dumps({"options": options}, ensure_ascii=False)


def test_generator_preserves_valid_items_and_repairs_only_bad_slot() -> None:
    long_text = "This option is deliberately far too long because it contains far more than sixteen measured words for repair"
    client = SequenceClient(
        [
            _payload(
                [
                    {"text": "Review key terms", "effects": {"knowledge": 3}},
                    {"text": "Ask a trusted ally", "effects": {"mood": 2}},
                    {"text": long_text, "effects": {"energy": -2}},
                ]
            ),
            _payload(
                [
                    {"text": "Pause and assess risk", "effects": {"knowledge": 2}},
                ]
            ),
        ]
    )

    event = OptionGenerator(client).generate_options_only(
        story_description="The partners wait for a decision about the agreement.",
        player_state={},
        language="en",
        retry_count=2,
    )

    assert [option.text for option in event.options] == [
        "Review key terms",
        "Ask a trusted ally",
        "Pause and assess risk",
    ]
    assert len(client.calls) == 2
    assert "Review key terms" in client.calls[1]["user_prompt"]
    assert long_text not in [option.text for option in event.options]


def test_failed_repair_keeps_valid_items_and_fills_only_missing_slot() -> None:
    client = SequenceClient(
        [
            _payload(
                [
                    {"text": "细读合作条款", "effects": {"knowledge": 3}},
                    {"text": "请伙伴一起把关", "effects": {"mood": 2}},
                    {"text": "长" * 41, "effects": {"energy": -2}},
                ]
            ),
            "not json",
        ]
    )

    event = OptionGenerator(client).generate_options_only(
        story_description="团队正在讨论合作协议。",
        player_state={},
        language="zh",
        retry_count=2,
    )

    assert len(event.options) == 3
    assert [option.text for option in event.options[:2]] == [
        "细读合作条款",
        "请伙伴一起把关",
    ]
    assert event.options[2].text == "先锁定关键风险"


def test_fast_option_budget_falls_back_without_discarding_complete_story() -> None:
    client = SequenceClient(
        [
            _payload(
                [
                    {"text": "细读合作条款", "effects": {"knowledge": 3}},
                    {"text": "长" * 41, "effects": {"energy": -2}},
                ]
            )
        ]
    )
    tracker = GenerationCallTracker(
        resolve_narrative_budget("round", "generate", "fast", "zh")
    )

    event = OptionGenerator(client).generate_options_only(
        story_description="团队正在讨论合作协议。",
        player_state={},
        language="zh",
        retry_count=2,
        generation_tracker=tracker,
    )

    assert event.event_description == "团队正在讨论合作协议。"
    assert len(event.options) == 3
    assert event.options[0].text == "细读合作条款"
    assert len(client.calls) == 1


def test_saved_legacy_two_to_four_option_groups_remain_valid() -> None:
    for count in (2, 3, 4):
        event = GameEvent(
            event_description="legacy",
            options=[
                EventOption(text=f"legacy {index}", effects={})
                for index in range(count)
            ],
        )
        assert len(event.options) == count


def test_nonstandard_new_event_paths_are_normalized_to_three_options() -> None:
    four = [EventOption(text=f"具体行动{index}", effects={}) for index in range(4)]
    two = [EventOption(text=f"已有行动{index}", effects={}) for index in range(2)]

    normalized_four = OptionGenerator.complete_new_event_options(
        four, story_description="眼前需要决定下一步。", language="zh"
    )
    normalized_two = OptionGenerator.complete_new_event_options(
        two, story_description="眼前需要决定下一步。", language="zh"
    )

    assert [option.text for option in normalized_four] == [
        "具体行动0",
        "具体行动1",
        "具体行动2",
    ]
    assert [option.text for option in normalized_two[:2]] == ["已有行动0", "已有行动1"]
    assert len(normalized_two) == 3


def test_default_option_repair_uses_two_calls_but_never_exceeds_two_without_tracker() -> (
    None
):
    client = SequenceClient(
        [
            _payload(
                [
                    {"text": "核对协议关键条款", "effects": {"knowledge": 3}},
                    {"text": "请同伴交叉检查", "effects": {"mood": 2}},
                    {"text": "长" * 41, "effects": {"energy": -2}},
                ]
            ),
            _payload([{"text": "先确认最坏风险", "effects": {"knowledge": 2}}]),
            _payload([]),
        ]
    )

    event = OptionGenerator(client).generate_options_only(
        story_description="团队正在讨论合作协议。",
        player_state={},
        language="zh",
    )

    assert len(event.options) == 3
    assert [option.text for option in event.options] == [
        "核对协议关键条款",
        "请同伴交叉检查",
        "先确认最坏风险",
    ]
    assert len(client.calls) == 2

    exhausted_client = SequenceClient(["not json"] * 5)
    fallback_event = OptionGenerator(exhausted_client).generate_options_only(
        story_description="团队正在讨论合作协议。",
        player_state={},
        language="zh",
        retry_count=5,
    )
    assert len(fallback_event.options) == 3
    assert len(exhausted_client.calls) == 2


def test_contextual_fallback_survives_recent_history_exhausting_static_pool() -> None:
    recent_choices = [
        "细读合作条款",
        "请伙伴一起把关",
        "先锁定关键风险",
        "先观察局势变化",
        "与当事人确认细节",
        "保留余地再做决定",
    ]
    client = SequenceClient(["not json", "still not json"])

    event = OptionGenerator(client).generate_options_only(
        story_description="团队正在讨论合作协议。",
        player_state={
            "decision_history": [{"choice": choice} for choice in recent_choices]
        },
        language="zh",
    )

    assert event.event_description == "团队正在讨论合作协议。"
    assert len(event.options) == 3
    assert not ({option.text for option in event.options} & set(recent_choices))
    assert all("方案" not in option.text for option in event.options)
    assert len(
        {
            tuple(sorted(option.effects.items()))
            for option in event.options
        }
    ) == 3


def test_english_repair_threshold_is_measured_in_words_not_characters() -> None:
    sixteen_words = (
        "Carefully review every relevant contract clause with two trusted advisers "
        "before making the final commitment today"
    )
    event = GameEvent(
        event_description="A contract decision must be made.",
        options=[
            EventOption(text=sixteen_words, effects={"knowledge": 3}),
            EventOption(text="Ask a trusted adviser", effects={"mood": 2}),
            EventOption(text="Delay the final commitment", effects={"energy": 2}),
        ],
    )

    issues = OptionGenerator(object()).validate_options_consistency(
        event,
        story_description=event.event_description,
        language="en",
    )

    assert not [issue for issue in issues if "too long" in issue]


def test_week_40_preset_new_events_are_normalized_to_three_in_both_languages() -> None:
    generator = object.__new__(EventGenerator)
    generator.preset_events = generator._load_preset_events()

    for language in ("zh", "en"):
        event = generator._get_preset_milestone_event(40, language)
        assert event is not None
        assert len(event.options) == 3


def test_scheduled_event_preserves_story_when_one_option_sibling_is_malformed() -> None:
    story = (
        "林岚按约来到档案馆，与周老师逐页核对账册来源，并在闭馆前确认了下一步调查方向。"
    )

    class Client:
        def call(self, **_: Any) -> str:
            return _payload(
                [
                    {"text": "继续核对账册来源", "effects": {"knowledge": 4}},
                    "malformed sibling",
                    {"text": "请周老师交叉验证", "effects": {"mood": 2}},
                ]
            ).replace(
                '{"options":', f'{{"event_description": {json.dumps(story)}, "options":'
            )

    class PlayerState:
        def to_dict(self) -> dict[str, Any]:
            return {
                "player_name": "林岚",
                "week": 2,
                "current_round": 1,
                "character_settings": {},
            }

    generator = RoundEventGenerator(
        player_state_getter=lambda: None,
        ai_generator=SimpleNamespace(ai_client=Client()),
        language_getter=lambda: "zh",
        character_introduction_service=None,
        summary_selector=None,
        relationship_service=None,
    )
    event = generator._generate_scheduled_event(
        [{"description": "核对账册", "parties": ["林岚", "周老师"]}],
        PlayerState(),
    )

    assert event is not None
    assert event.event_description == story
    assert len(event.options) == 3
