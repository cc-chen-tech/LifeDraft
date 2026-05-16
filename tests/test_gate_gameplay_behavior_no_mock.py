"""No-mock gameplay behavior tests for option relevance and text cleanup."""

import pytest

from config.prompts import get_story_only_prompt
from src.ai.models import EventOption, GameEvent
from src.ai.option_generator import OptionGenerator
from src.ai.story_generator import StoryGenerator
from src.ai.text_quality import (normalize_chinese_punctuation,
                                 normalize_generated_story,
                                 validate_narrative_quality)


def test_option_generator_rejects_generic_options_for_specific_decision_point() -> None:
    event = GameEvent(
        event_description=(
            "苏小二把潮湿的账册推到桌边，压低声音问："
            "“你现在要不要跟我去码头，把交货人当场截住？”"
        ),
        options=[
            EventOption(text="保持平常心继续前进", effects={"energy": 0, "mood": 0}),
            EventOption(text="积极面对新的一天", effects={"energy": -5, "mood": 5}),
        ],
    )

    with pytest.raises(ValueError, match="generic"):
        OptionGenerator.ensure_options_consistency(
            event=event,
            story_description=event.event_description,
            available_people=["苏小二"],
            language="zh",
        )


def test_option_generator_accepts_options_tied_to_story_decision_point() -> None:
    event = GameEvent(
        event_description=(
            "苏小二把潮湿的账册推到桌边，压低声音问："
            "“你现在要不要跟我去码头，把交货人当场截住？”"
        ),
        options=[
            EventOption(text="跟苏小二去码头截人", effects={"energy": -8, "mood": 2}),
            EventOption(text="留下核对账册暗号", effects={"knowledge": 6, "mood": -2}),
        ],
    )

    OptionGenerator.ensure_options_consistency(
        event=event,
        story_description=event.event_description,
        available_people=["苏小二"],
        language="zh",
    )


def test_chinese_punctuation_normalizer_cleans_dialogue_artifacts() -> None:
    raw = '他说: "你真的要去吗?" 她停了一下, 说: "现在就走."'

    assert (
        normalize_chinese_punctuation(raw) == "他说：“你真的要去吗？” 她停了一下，说：“现在就走。”"
    )


def test_generated_story_normalizer_removes_internal_state_leaks_and_over_fragmentation() -> None:
    raw = (
        "【状态】energy -5, mood +3\n"
        "你推开门。\n"
        "雨声停了。\n"
        "账册还在。\n"
        "你看见苏小二站在檐下。\n"
        "他把油纸伞递过来。\n"
    )

    cleaned = normalize_generated_story(raw, language="zh", perspective="second")

    assert "energy" not in cleaned
    assert "mood" not in cleaned
    assert "【状态】" not in cleaned
    assert cleaned.count("\n\n") <= 2
    assert "你推开门。雨声停了。" in cleaned


def test_narrative_quality_rejects_mixed_perspective_and_internal_leaks() -> None:
    text = "你走进铺子。\n\n我忽然想起系统判定：mood +5，wealth -10。"

    issues = validate_narrative_quality(text, language="zh", perspective="second")

    assert "mixed_perspective" in issues
    assert "internal_state_leak" in issues


def test_story_prompt_includes_world_model_location_career_and_repetition_constraints() -> None:
    player_state = {
        "player_name": "林舟",
        "week": 8,
        "world_model_data": {
            "character_locations": {
                "林舟": {
                    "location": "上海徐汇区的工作室",
                    "region": "上海",
                    "since_week": 4,
                    "travel_mode": "resident",
                },
                "周岚": {
                    "location": "杭州西湖边的住处",
                    "region": "杭州",
                    "since_week": 6,
                    "travel_mode": "resident",
                },
            },
            "career_records": {
                "林舟": {
                    "current_job": "初级产品经理",
                    "employer": "海桐科技",
                    "level": "junior",
                    "since_week": 2,
                    "history": [],
                }
            },
        },
    }

    world_model = StoryGenerator._build_world_model_from_state_dict(player_state)
    prompt = get_story_only_prompt(
        player_state=player_state,
        language="zh",
        character_settings={"relationships": {"key_people": [{"name": "周岚", "role": "朋友"}]}},
        world_model=world_model,
        overused_phrases="【动态禁用】不要再用“晨光熹微”。",
    )

    assert "林舟 当前位置：上海徐汇区的工作室" in prompt
    assert "周岚 当前位置：杭州西湖边的住处" in prompt
    assert "两个在不同地点的角色不能在同一物理场景中对话或互动" in prompt
    assert "林舟：初级产品经理（海桐科技），级别=junior" in prompt
    assert "职位变动必须合理递进" in prompt
    assert "不要再用“晨光熹微”" in prompt
