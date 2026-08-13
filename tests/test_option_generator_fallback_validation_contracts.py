"""Provider-free contracts for option fallback and validation logic."""

from src.ai.models import EventOption, GameEvent
from src.ai.option_generator import OptionGenerator


def test_contextual_fallback_options_select_story_specific_chinese_choices() -> None:
    cases = [
        ("团队正在讨论合作协议和签约风险。", "细读合作条款"),
        ("用户调研报告和数据反馈需要核验。", "整理用户数据"),
        ("明天要在会议上汇报提案方案。", "完善方案细节"),
        ("雨停后，林岚重新审视眼前局面。", "梳理刚发生的变化"),
    ]

    for story, expected_first_option in cases:
        options = OptionGenerator.build_contextual_fallback_options(story, language="zh")

        assert len(options) == 3
        assert options[0].text == expected_first_option
        assert all(set(option.effects) <= {"energy", "mood", "knowledge"} for option in options)


def test_contextual_fallback_options_are_safe_for_english_stories() -> None:
    options = OptionGenerator.build_contextual_fallback_options(
        "A quiet moment before the next decision.", language="en"
    )

    assert [option.text for option in options] == [
        "Review the key terms",
        "Ask an ally to cross-check",
        "Identify the next risk",
    ]
    assert options[1].effects == {"energy": -5, "mood": 4, "knowledge": 5}


def test_relationship_normalization_and_quality_defaults_preserve_option_effects() -> None:
    generator = OptionGenerator(client=None)
    event = GameEvent(
        event_description="林岚准备和 Ada 讨论档案。",
        options=[
            EventOption(text="确认 Ada 的建议", effects={"relationships": {"ada": 2}}),
            EventOption(text="请导师审阅", effects={"relationships": {"导师": 3}}),
            EventOption(text="联系新同事", effects={"relationships": {"新同事": 1}}),
        ],
    )
    settings = {
        "relationships": {"key_people": [{"name": "Ada", "role": "导师"}]},
        "family": {"family_members": [{"name": "母亲"}]},
    }

    generator.validate_and_fix_relationships(event, settings)
    generator.validate_event_quality(event)

    assert event.options[0].effects["relationships"] == {"Ada": 2}
    assert event.options[1].effects["relationships"] == {"Ada": 3}
    assert event.options[2].effects["relationships"] == {"新同事": 1}
