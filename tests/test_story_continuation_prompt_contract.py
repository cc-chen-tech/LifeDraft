"""Story continuation prompt contract tests."""

from config.prompts.story_prompts import get_result_generation_prompt
import pytest

pytestmark = [pytest.mark.unit]



def test_chinese_choice_continuation_prompt_requires_third_person():
    """选择结果续写应延续主线第三人称叙事，不能要求第二人称。"""
    prompt = get_result_generation_prompt(
        event_description="林见微站在茶楼门口，沈伯安问她是否愿意同行。",
        chosen_option="谨慎追问其身份缘由",
        effects={"knowledge": 5},
        language="zh",
        character_settings={"identity": {"name": "林见微"}},
    )

    assert "第三人称" in prompt
    assert "林见微" in prompt
    assert "第二人称叙事" not in prompt
    assert "你\"的视角" not in prompt


def test_chinese_choice_continuation_prompt_forbids_repeating_current_story():
    """选择结果续写不应重写当前事件正文，只能从玩家选择处继续。"""
    prompt = get_result_generation_prompt(
        event_description="林见微已经抵达怀远驿，郑冲告知手札三日前被官差取走。",
        chosen_option="追问郑冲，索要留页",
        effects={"knowledge": 10},
        language="zh",
        character_settings={"identity": {"name": "林见微"}},
    )

    assert "不得重复" in prompt or "不要重复" in prompt
    assert "当前故事" in prompt
    assert "从玩家选择之后" in prompt or "从这个选择之后" in prompt


def test_english_choice_continuation_prompt_requires_third_person():
    """English continuation prompt should match the same third-person contract."""
    prompt = get_result_generation_prompt(
        event_description="Lin Jianwei stands at the teahouse door.",
        chosen_option="Ask carefully who the person is",
        effects={"knowledge": 5},
        language="en",
        character_settings={"identity": {"name": "Lin Jianwei"}},
    )

    assert "third-person" in prompt.lower()
    assert "Lin Jianwei" in prompt
    assert "second-person" not in prompt.lower()
