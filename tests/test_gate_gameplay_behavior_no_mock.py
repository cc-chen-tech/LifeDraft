"""No-mock gameplay behavior tests for option relevance and text cleanup."""

import pytest
from unittest.mock import MagicMock

from config.prompts import (
    get_opening_story_prompt,
    get_round_event_prompt,
    get_story_only_prompt,
)
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


def test_story_prompts_pin_player_identity_from_state_and_character_settings() -> None:
    player_state = {
        "player_name": "林见微",
        "age": 23,
        "week": 0,
        "current_round": 0,
        "rounds_per_week": 3,
    }
    character_settings = {
        "era": {"year": 690, "era_description": "唐代神都洛阳"},
        "gender": {"gender": "女", "gender_description": "女性"},
        "world": {"world_description": "古代宫廷与市井交错"},
        "family": {"family_description": "书香门第"},
        "traits": {"traits_description": "谨慎敏锐"},
    }

    story_prompt = get_story_only_prompt(
        player_state=player_state,
        language="zh",
        character_settings=character_settings,
    )
    round_prompt = get_round_event_prompt(
        player_state=player_state,
        language="zh",
        round_number=0,
        round_context="",
        character_settings=character_settings,
    )

    for prompt in (story_prompt, round_prompt):
        assert "主角名称是：林见微" in prompt
        assert "禁止编造其他名字" in prompt
        assert "性别：女" in prompt


def test_opening_story_prompt_forbids_replacing_player_with_template_hero() -> None:
    prompt = get_opening_story_prompt(
        character_settings={
            "era": {"year": 690, "era_description": "唐代神都洛阳"},
            "gender": {"gender": "女", "gender_description": "女性"},
            "world": {"world_description": "古代宫廷与市井交错"},
        },
        player_name="林见微",
        life_vision="查明家族旧案",
        formatted_family_members="母亲：林夫人",
        language="zh",
    )

    assert "主角姓名必须是：林见微" in prompt
    assert "绝对禁止把主角改名为狄仁杰" in prompt
    assert "主角性别必须是：女" in prompt


def test_opening_story_prompt_anchors_first_week_date_and_season() -> None:
    prompt = get_opening_story_prompt(
        character_settings={
            "era": {"year": 2024, "era_description": "2024年中国互联网行业"},
            "gender": {"gender": "女"},
            "world": {"world_description": "杭州AI协作工具创业公司"},
        },
        player_name="顾晨曦",
        life_vision="2020年代中国互联网公司，成为AI协作工具产品经理",
        formatted_family_members="母亲：周梅",
        language="zh",
    )

    assert "2024年1月第1周" in prompt
    assert "冬季" in prompt
    assert "禁止写成夏季" in prompt


def test_round_event_fallback_remains_substantial_story_when_generation_fails() -> None:
    class FailingClient:
        def call(self, **_kwargs):
            raise RuntimeError("AI unavailable")

    event = StoryGenerator(FailingClient()).generate_round_event(
        player_state={
            "player_name": "林见微",
            "age": 22,
            "week": 1,
            "current_round": 0,
        },
        language="zh",
        round_number=0,
        round_context="",
        character_settings={
            "era": {"era_description": "唐代神都洛阳"},
            "traits": {"traits_description": "谨慎敏锐"},
        },
        option_generator=OptionGenerator(FailingClient()),
    )

    assert len(event.event_description) > 100
    assert event.event_description.endswith("。")
    assert "林见微" in event.event_description
    assert len(event.options) == 3


def test_round_event_retries_when_story_ignores_all_key_people_and_fabricates_new_cast() -> None:
    class DriftClient:
        def __init__(self):
            self.calls = []

        def call(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return (
                    "马老板把欠条拍在桌上，方蕾和赵子豪站在苏州贸易公司的门口，"
                    "王丽华低声催促主角马上接管父亲留下的债务。"
                )
            return (
                "陆昊然把产品评审文档推到林见微面前，陈晓雨提醒她先确认用户反馈，"
                "林一凡则把远程会议链接发进群里。"
            )

    client = DriftClient()
    gen = StoryGenerator(client)
    mock_option_gen = MagicMock()
    mock_option_gen.generate_options_only.return_value = GameEvent(
        event_description="",
        options=[
            EventOption(text="先和陆昊然核对需求", effects={"knowledge": 5}),
            EventOption(text="请陈晓雨一起复盘用户反馈", effects={"mood": 2}),
        ],
    )
    mock_option_gen.validate_and_fix_relationships.return_value = None
    mock_option_gen.validate_options_consistency.return_value = []

    gen.generate_round_event(
        player_state={
            "game_id": 7,
            "player_name": "林见微",
            "age": 22,
            "week": 1,
            "current_round": 0,
        },
        language="zh",
        round_number=0,
        round_context="第一周周一，产品新人入职后的第一次需求评审。",
        character_settings={
            "relationships": {
                "key_people": [
                    {"name": "陆昊然", "role": "导师"},
                    {"name": "陈晓雨", "role": "同事"},
                    {"name": "林一凡", "role": "朋友"},
                ]
            }
        },
        option_generator=mock_option_gen,
    )

    assert len(client.calls) == 2
    retry_prompt = client.calls[1]["user_prompt"]
    assert "上一版故事完全没有使用预设关键人物" in retry_prompt
    story_for_options = mock_option_gen.generate_options_only.call_args.kwargs[
        "story_description"
    ]
    assert "陆昊然" in story_for_options
    assert "马老板" not in story_for_options
