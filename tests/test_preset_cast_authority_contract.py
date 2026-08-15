"""Contract tests for preset relationship authority in story generation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from config.prompts.story_prompts import (
    get_event_generation_prompt,
    get_result_generation_prompt,
    get_round_event_prompt,
    get_story_only_prompt,
)
from src.ai.models import EventOption, GameEvent
from src.ai.story_exceptions import StoryGenerationFailure
from src.game.round.event_generator import RoundEventGenerator
from src.game.world_model import WorldModel


def _modern_product_manager_settings() -> dict[str, Any]:
    return {
        "era": {
            "year": 2026,
            "era_description": "现代都市",
            "world_context": "互联网产品团队快速迭代。",
        },
        "age": {"age": 25, "age_description": "职场成长期"},
        "gender": {"gender": "女", "gender_description": "现代都市女性"},
        "occupation": {
            "occupation": "产品经理",
            "employer": "星河科技",
            "level": "junior",
        },
        "relationships": {
            "relationships_description": "围绕产品经理成长的导师、闺蜜和同期网络。",
            "key_people": [
                {
                    "name": "陆昊然",
                    "role": "导师",
                    "relationship": "导师",
                    "description": "资深产品负责人，负责指导主角复盘需求判断。",
                },
                {
                    "name": "陈晓雨",
                    "role": "闺蜜",
                    "relationship": "闺蜜",
                    "description": "大学好友，理解主角的职场压力。",
                },
                {
                    "name": "林一凡",
                    "role": "同期",
                    "relationship": "同期",
                    "description": "同批入职的产品同事，与主角共同成长。",
                },
            ],
        },
        "traits": {"traits_description": "认真、敏感、希望成长为可靠的产品负责人。"},
    }


def _modern_product_manager_settings_with_legacy_relationships_list() -> dict[str, Any]:
    settings = _modern_product_manager_settings()
    settings["relationships"] = settings["relationships"]["key_people"]
    return settings


def _modern_product_manager_settings_with_relation_field() -> dict[str, Any]:
    settings = _modern_product_manager_settings()
    settings["relationships"] = {
        "relationships_description": "围绕产品经理成长的导师、闺蜜和同期网络。",
        "key_people": [
            {
                "name": "陆昊然",
                "relation": "导师",
                "description": "资深产品负责人，负责指导主角复盘需求判断。",
            },
            {
                "name": "陈晓雨",
                "relation": "闺蜜",
                "description": "大学好友，理解主角的职场压力。",
            },
            {
                "name": "林一凡",
                "relation": "同期",
                "description": "同批入职的产品同事，与主角共同成长。",
            },
        ],
    }
    return settings


def _modern_product_manager_settings_with_family() -> dict[str, Any]:
    settings = _modern_product_manager_settings()
    settings["family"] = {
        "family_members": [
            {
                "name": "林建国",
                "role": "父亲",
                "relationship": "父亲",
                "description": "支持主角职业选择的父亲。",
            },
            {
                "name": "王丽华",
                "role": "母亲",
                "relationship": "母亲",
                "description": "关心主角生活节奏的母亲。",
            },
        ]
    }
    return settings


def _player_state() -> dict[str, Any]:
    return {
        "age": 25,
        "week": 1,
        "current_round": 0,
        "rounds_per_week": 3,
        "energy": 72,
        "mood": 61,
        "knowledge": 58,
        "wealth": 50000,
        "relationships": {"陆昊然": 35, "陈晓雨": 80, "林一凡": 45},
    }


def test_required_cast_constraints_include_all_preset_people() -> None:
    from src.game.relationship_authority import build_required_cast_constraints

    text = build_required_cast_constraints(_modern_product_manager_settings(), "zh")

    assert "预设关键人物" in text
    assert "陆昊然" in text
    assert "导师" in text
    assert "陈晓雨" in text
    assert "闺蜜" in text
    assert "林一凡" in text
    assert "同期" in text
    assert "不得改名" in text
    assert "不得替换" in text
    assert "至少使用1位预设关键人物" in text
    assert "陆昊然、陈晓雨、林一凡至少一位" in text
    assert "80%" in text
    assert "预设关系网" in text
    assert "苏婉清" not in text


def test_story_only_prompt_injects_required_cast_authority() -> None:
    prompt = get_story_only_prompt(
        player_state=_player_state(),
        language="zh",
        character_settings=_modern_product_manager_settings(),
        last_event_description="陈晓雨陪你复盘了昨天的需求评审。",
    )

    assert "预设关键人物" in prompt
    assert "陆昊然" in prompt
    assert "导师" in prompt
    assert "陈晓雨" in prompt
    assert "闺蜜" in prompt
    assert "林一凡" in prompt
    assert "同期" in prompt
    assert "不得改名" in prompt
    assert "不得替换" in prompt
    assert "至少使用1位预设关键人物" in prompt
    assert "陆昊然、陈晓雨、林一凡至少一位" in prompt


def test_round_event_prompt_injects_required_cast_authority() -> None:
    prompt = get_round_event_prompt(
        player_state=_player_state(),
        language="zh",
        round_number=0,
        round_context="上一轮你决定向导师请教需求优先级。",
        character_settings=_modern_product_manager_settings(),
    )

    assert "预设关键人物" in prompt
    assert "陆昊然" in prompt
    assert "导师" in prompt
    assert "陈晓雨" in prompt
    assert "闺蜜" in prompt
    assert "林一凡" in prompt
    assert "同期" in prompt
    assert "不得改名" in prompt
    assert "不得替换" in prompt
    assert "至少使用1位预设关键人物" in prompt
    assert "陆昊然、陈晓雨、林一凡至少一位" in prompt


def test_weekly_event_prompt_injects_required_cast_authority() -> None:
    """The legacy weekly event path must not be weaker than round events."""
    prompt = get_event_generation_prompt(
        player_state=_player_state(),
        language="zh",
        current_phase="early_career",
        character_settings=_modern_product_manager_settings(),
        last_event_description="陈晓雨陪你复盘了昨天的需求评审。",
    )

    assert "预设关键人物" in prompt
    assert "陆昊然" in prompt
    assert "导师" in prompt
    assert "陈晓雨" in prompt
    assert "闺蜜" in prompt
    assert "林一凡" in prompt
    assert "同期" in prompt
    assert "不得改名" in prompt
    assert "不得替换" in prompt
    assert "至少使用1位预设关键人物" in prompt
    assert "陆昊然、陈晓雨、林一凡至少一位" in prompt


def test_round_event_prompt_injects_required_cast_authority_from_relationships_list() -> None:
    prompt = get_round_event_prompt(
        player_state=_player_state(),
        language="zh",
        round_number=0,
        round_context="上一轮你决定向导师请教需求优先级。",
        character_settings=_modern_product_manager_settings_with_legacy_relationships_list(),
    )

    assert "预设关键人物" in prompt
    assert "陆昊然" in prompt
    assert "导师" in prompt
    assert "陈晓雨" in prompt
    assert "闺蜜" in prompt
    assert "林一凡" in prompt
    assert "同期" in prompt
    assert "不得改名" in prompt
    assert "不得替换" in prompt
    assert "至少使用1位预设关键人物" in prompt
    assert "陆昊然、陈晓雨、林一凡至少一位" in prompt


def test_relation_field_is_treated_as_required_cast_role() -> None:
    """Frontend and older DB payloads may use relation instead of role."""
    from src.game.relationship_authority import build_required_cast_constraints

    text = build_required_cast_constraints(
        _modern_product_manager_settings_with_relation_field(),
        "zh",
    )

    assert "陆昊然：导师" in text
    assert "陈晓雨：闺蜜" in text
    assert "林一凡：同期" in text
    assert "：关键人物" not in text
    assert "导师；导师" not in text


def test_available_people_prompt_uses_relation_field_as_role_label() -> None:
    """The prompt must not list relation-only people as empty-role names."""
    prompt = get_round_event_prompt(
        player_state=_player_state(),
        language="zh",
        round_number=0,
        round_context="上一轮你决定向导师请教需求优先级。",
        character_settings=_modern_product_manager_settings_with_relation_field(),
    )

    assert "陆昊然（导师）" in prompt
    assert "陈晓雨（闺蜜）" in prompt
    assert "林一凡（同期）" in prompt
    assert "陆昊然（）" not in prompt
    assert "陈晓雨（）" not in prompt
    assert "林一凡（）" not in prompt


def test_quick_validator_uses_relationships_list_for_required_cast() -> None:
    from config.prompts._helpers import _collect_available_people
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings_with_legacy_relationships_list()
    available_people = [
        person["name"]
        for person in _collect_available_people(settings)
        if person.get("name")
    ]

    result = quick_validate_story(
        story_text=(
            "马老板把欠条摊在会议桌上，方蕾要求林清立刻接手苏州贸易公司的债务。"
            "赵子豪在旁边翻出旧账，王丽华不断催促她签字。"
        ),
        character_settings=settings,
        available_people=available_people,
        language="zh",
    )

    assert not result.passed
    assert any("没有使用预设关键人物" in issue for issue in result.issues)


def test_quick_validator_rejects_unapproved_role_alias_with_single_preset_person() -> None:
    """A single configured person must not permit a new named relative to lead a scene."""
    from src.ai.quick_validator import quick_validate_story

    settings = {
        "relationships": {
            "key_people": [
                {"name": "王天成", "role": "创业伙伴", "relationship": "伙伴"},
            ]
        }
    }

    result = quick_validate_story(
        story_text=(
            "周叔端着生煎走进咖啡馆，催林澈立刻放下访谈计划。"
            "王天成只能坐在一旁，整件事都由周叔安排。"
        ),
        character_settings=settings,
        available_people=["王天成"],
        language="zh",
    )

    assert not result.passed
    assert any("名单外命名角色" in issue for issue in result.issues)


def test_quick_validator_warns_for_two_of_three_key_people_with_heuristic_names() -> None:
    """A majority preset cast must not be rejected by surname-shaped object names."""
    from config.prompts._helpers import _collect_available_people
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    available_people = [
        person["name"]
        for person in _collect_available_people(settings)
        if person.get("name")
    ]
    available_people.append("孙悟空")

    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨同孙悟空核对方案。"
            "安神香是产品代号，雷火阵是风控模块，云梯果是测试数据集。"
            "三人查看材料后约定明天继续讨论。"
        ),
        character_settings=settings,
        available_people=available_people,
        language="zh",
    )

    assert result.passed
    assert result.issues == []
    assert any("要求多人关系戏至少80%" in warning for warning in result.warnings)


def test_quick_validator_rejects_invented_cast_that_drives_the_plot() -> None:
    """A majority mention cannot hide three new people doing the core work."""
    from config.prompts._helpers import _collect_available_people
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    available_people = [
        person["name"]
        for person in _collect_available_people(settings)
        if person.get("name")
    ]

    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨在开场打过招呼便离开会议室。"
            "赵子豪制定了完整方案，方蕾分配了所有任务，马文涛批准预算并确定上线日期。"
            "接下来的项目完全按照这三人的安排执行。"
        ),
        character_settings=settings,
        available_people=available_people,
        language="zh",
    )

    assert not result.passed
    assert any("名单外人物主导剧情" in issue for issue in result.issues)


def test_quick_validator_warns_for_action_bearing_product_labels() -> None:
    """Product labels with operational verbs are not established as people."""
    from config.prompts._helpers import _collect_available_people
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    available_people = [
        person["name"]
        for person in _collect_available_people(settings)
        if person.get("name")
    ]

    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨一起核对产品方案。"
            "安神香负责睡眠场景，雷火阵执行风控检查，云梯果是测试数据集。"
            "两人确认这些模块运行正常后结束会议。"
        ),
        character_settings=settings,
        available_people=available_people,
        language="zh",
    )

    assert result.passed
    assert result.issues == []
    assert any("要求多人关系戏至少80%" in warning for warning in result.warnings)


def test_quick_validator_warns_for_explicit_non_person_governance_actors() -> None:
    """Explicit product/module/data labels remain non-person actors."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨一起核对产品方案。"
            "安神香是产品代号，随后安神香制定睡眠方案；"
            "雷火阵是风控模块，接着雷火阵安排检查任务；"
            "云梯果是测试数据集。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert result.passed
    assert result.issues == []
    assert any("要求多人关系戏至少80%" in warning for warning in result.warnings)


def test_quick_validator_rejects_long_governance_action_descriptions() -> None:
    """Actor scanning must retain the full lookahead allowed by action regexes."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨在开场打过招呼便离开会议室。"
            "赵强制定了一个经过多轮讨论审核的完整产品方案，"
            "方蕾安排了一个经过多轮讨论审核的完整检查任务，"
            "马涛只负责记录会议结论。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert not result.passed
    assert any("名单外人物主导剧情" in issue for issue in result.issues)


def test_quick_validator_rejects_plot_drivers_after_consumed_modifiers() -> None:
    """Greedy name matching must not hide modifiers before core actions."""
    from config.prompts._helpers import _collect_available_people
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    available_people = [
        person["name"]
        for person in _collect_available_people(settings)
        if person.get("name")
    ]

    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨在开场打过招呼便离开会议室。"
            "赵强立即制定了完整方案，方蕾随后分配了所有任务，马涛最终批准预算。"
            "接下来的项目完全按照这三人的安排执行。"
        ),
        character_settings=settings,
        available_people=available_people,
        language="zh",
    )

    assert not result.passed
    assert any("名单外人物主导剧情" in issue for issue in result.issues)


def test_quick_validator_deduplicates_one_actor_across_consumed_actions() -> None:
    """One omitted protagonist must not count as three outside plot drivers."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨一起参加项目会议。"
            "陈越制定了完整方案，陈越分配了所有任务，陈越批准了项目预算。"
            "三人确认安排后结束会议。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert result.passed
    assert result.issues == []
    assert result.warnings == []


def test_quick_validator_rejects_plot_drivers_after_discourse_markers() -> None:
    """Discourse markers immediately before outside names are valid boundaries."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨在开场打过招呼便离开会议室。"
            "随后赵强制定方案，接着方蕾分配任务，最后马文涛批准预算。"
            "接下来的项目完全按照这三人的安排执行。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert not result.passed
    assert any("名单外人物主导剧情" in issue for issue in result.issues)


def test_quick_validator_rejects_plot_drivers_after_surname_shaped_markers() -> None:
    """Surname-shaped discourse markers must not consume the following actors."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨在开场打过招呼便离开会议室。"
            "于是赵强制定方案，此时方蕾分配任务，最后马涛批准预算。"
            "接下来的项目完全按照这三人的安排执行。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert not result.passed
    assert any("名单外人物主导剧情" in issue for issue in result.issues)


def test_quick_validator_rejects_coordinated_outside_plot_drivers() -> None:
    """Conjunction-delimited outside actors still count toward cast drift."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨在开场打过招呼便离开会议室。"
            "赵强与方蕾共同制定方案，马涛批准预算并确定上线日期。"
            "接下来的项目完全按照这三人的安排执行。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert not result.passed
    assert any("名单外人物主导剧情" in issue for issue in result.issues)


def test_quick_validator_treats_technical_occupations_as_people() -> None:
    """Technical occupation nouns do not establish an object identity."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨在开场打过招呼便离开会议室。"
            "赵强是模型专家，随后赵强制定方案；"
            "方蕾是模型工程师，接着方蕾分配任务；"
            "马涛只负责记录会议结论。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert not result.passed
    assert any("名单外人物主导剧情" in issue for issue in result.issues)


def test_quick_validator_deduplicates_marker_actor_before_cast_threshold() -> None:
    """Marker-extracted variants of one omitted protagonist count only once."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然参加了项目会议。"
            "随后陈越制定了完整方案，接着陈越分配了所有任务，最后陈越批准了预算。"
            "两人确认安排后结束会议。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert result.passed
    assert result.issues == []


def test_quick_validator_deduplicates_one_character_modifier_variants() -> None:
    """One-character modifiers must not turn one actor into three names."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨一起参加项目会议。"
            "陈越又制定了完整方案，陈越还分配了所有任务，陈越则批准了预算。"
            "三人确认安排后结束会议。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert result.passed
    assert result.issues == []


def test_quick_validator_attributes_joint_action_to_both_outside_actors() -> None:
    """Both coordinated actors own a governance action performed jointly."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨在开场打过招呼便离开会议室。"
            "赵强与方蕾共同制定方案，马涛负责记录会议结论。"
            "接下来的项目完全按照这三人的安排执行。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert not result.passed
    assert any("名单外人物主导剧情" in issue for issue in result.issues)


@pytest.mark.parametrize("modifier", ["协同", "联合"])
def test_quick_validator_attributes_all_supported_joint_modifiers(
    modifier: str,
) -> None:
    """Every modifier accepted by coordinated-name parsing owns the shared action."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨在开场打过招呼便离开会议室。"
            f"赵强与方蕾{modifier}制定方案，马涛批准预算。"
            "接下来的项目完全按照这三人的安排执行。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert not result.passed
    assert any("名单外人物主导剧情" in issue for issue in result.issues)


def test_quick_validator_ignores_predicate_after_discourse_marker() -> None:
    """An omitted-subject predicate after a marker is not a third outside person."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨在开场打过招呼便离开会议室。"
            "赵强制定方案，方蕾分配任务，随后安排会议。"
            "两名临时顾问完成工作后离开。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert result.passed
    assert result.issues == []


def test_quick_validator_ignores_surname_shaped_prose_suffixes() -> None:
    """Narrative text must not invent names from suffixes such as 元低声."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨坐在会议室里。林伯元低声提醒林清注意方向，"
            "会议气氛逐渐平稳，大家决定继续推进产品复盘。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert result.passed


def test_quick_validator_does_not_treat_weekend_phrase_as_invented_cast() -> None:
    """Calendar language must not trigger the strict relationship-network guard."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然把需求复盘表递给林清，提醒她先确认用户反馈。"
            "陈晓雨陪她梳理下午的访谈记录，并约好下次一起核对方案。"
            "周末的复盘仍由她们安排，林清决定先把今天的结论整理出来。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert result.passed


def test_quick_validator_ignores_surname_shaped_sentence_openers() -> None:
    """Normal prose must not turn sentence-opening adverbs into invented cast."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然和陈晓雨在会议室复盘项目。"
            "周围的灯光暗下来，于是陈越把预算表递给两人。"
            "安静地等了一会儿后，她们确认了下一步的测算安排。"
        ),
        character_settings=settings,
        available_people=["陈越", "陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert result.passed


def test_quick_validator_ignores_protagonist_verb_phrases_outside_relationship_cast() -> None:
    """The protagonist may be absent from relationship people without becoming fake cast."""
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    result = quick_validate_story(
        story_text=(
            "陆昊然在晨会前提醒团队核对风控模块的测试结果。"
            "陈越走进会议室。陈越脱下大衣。陈越抬头看向投影屏幕。"
            "她把昨晚整理的风险清单递给陆昊然，等待他的意见。"
        ),
        character_settings=settings,
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert result.passed


def test_quick_validator_ignores_protagonist_action_phrases_seen_in_live_retry() -> None:
    """Action prose must not make the protagonist look like several invented people."""
    from src.ai.quick_validator import QuickValidator

    validator = QuickValidator()
    candidates = validator._extract_likely_chinese_person_names(
        text=(
            "陈越也没有立刻回答。陈越收起手机，陈越坦然看向林悦。"
            "她随后陈越放下咖啡，陈越问赵思琪是否愿意一起梳理路线。"
            "陈越伸出手，等待两人的回应。"
        ),
        allowed_names=["林悦", "赵思琪"],
    )

    assert candidates == []


def test_quick_validator_rejects_single_new_role_substitute_for_preset_network() -> None:
    """A single invented strong-role character can still replace the preset network."""
    from config.prompts._helpers import _collect_available_people
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings()
    available_people = [
        person["name"]
        for person in _collect_available_people(settings)
        if person.get("name")
    ]

    result = quick_validate_story(
        story_text=(
            "陆昊然在会议室门口提醒林清先看用户反馈。"
            "苏婉清推开会议室的门，以投资人兼导师的身份接管了林清的产品复盘，"
            "陪她拆解路线、安抚情绪，并决定下一步融资节奏。"
            "整个下午，林清都跟着苏婉清推进主线，陈晓雨和林一凡没有参与。"
        ),
        character_settings=settings,
        available_people=available_people,
        language="zh",
    )

    assert not result.passed
    assert any("名单外关键角色替代预设关系网" in issue for issue in result.issues)


def test_quick_validator_rejects_family_only_story_when_key_people_are_missing() -> None:
    """Family members are available people, but they do not replace preset key people."""
    from config.prompts._helpers import _collect_available_people
    from src.ai.quick_validator import quick_validate_story

    settings = _modern_product_manager_settings_with_family()
    available_people = [
        person["name"]
        for person in _collect_available_people(settings)
        if person.get("name")
    ]

    result = quick_validate_story(
        story_text=(
            "林建国在早餐桌边提醒林清注意身体，王丽华把热粥推到她手边。"
            "这一整天都围绕父母对职业选择的担心展开，没有导师复盘、闺蜜支持或同期协作。"
        ),
        character_settings=settings,
        available_people=available_people,
        language="zh",
    )

    assert not result.passed
    assert any("没有使用预设关键人物" in issue for issue in result.issues)


def test_quick_validator_rejects_active_action_from_deceased_family_member() -> None:
    from config.prompts._helpers import _collect_available_people
    from src.ai.quick_validator import quick_validate_story

    settings = {
        "family": {
            "family_members": [
                {
                    "name": "顾建国",
                    "role": "父亲",
                    "relationship": "已故父亲",
                    "description": "三年前因病去世，只能作为回忆、遗物或旧照片出现。",
                },
                {
                    "name": "周梅",
                    "role": "母亲",
                    "relationship": "母亲",
                    "description": "仍与主角一起生活。",
                },
            ]
        },
        "relationships": {
            "key_people": [
                {"name": "陆昊然", "role": "导师", "relationship": "导师"},
                {"name": "陈晓雨", "role": "闺蜜", "relationship": "闺蜜"},
            ]
        },
    }
    available_people = [
        person["name"]
        for person in _collect_available_people(settings)
        if person.get("name")
    ]

    result = quick_validate_story(
        story_text=(
            "陆昊然刚把复盘表放到桌上，顾建国推门进来，把一份病历递给顾晨曦，"
            "低声说自己这几年一直在等她回家。陈晓雨惊讶地站起身。"
        ),
        character_settings=settings,
        available_people=available_people,
        language="zh",
    )

    assert not result.passed
    assert any("已故家庭成员" in issue and "顾建国" in issue for issue in result.issues)


def test_quick_validator_allows_deceased_family_member_as_memory_or_photo() -> None:
    from config.prompts._helpers import _collect_available_people
    from src.ai.quick_validator import quick_validate_story

    settings = {
        "family": {
            "family_members": [
                {
                    "name": "顾建国",
                    "role": "父亲",
                    "relationship": "已故父亲",
                    "description": "三年前因病去世，只能作为回忆、遗物或旧照片出现。",
                }
            ]
        },
        "relationships": {
            "key_people": [
                {"name": "陆昊然", "role": "导师", "relationship": "导师"},
                {"name": "陈晓雨", "role": "闺蜜", "relationship": "闺蜜"},
            ]
        },
    }
    available_people = [
        person["name"]
        for person in _collect_available_people(settings)
        if person.get("name")
    ]

    result = quick_validate_story(
        story_text=(
            "陆昊然把用户反馈贴到白板上，提醒顾晨曦先确认需求优先级。"
            "她看见桌角压着顾建国的旧照片，想起父亲去世前叮嘱她要把事情讲清楚。"
            "陈晓雨陪她把访谈记录重新排了一遍。"
        ),
        character_settings=settings,
        available_people=available_people,
        language="zh",
    )

    assert result.passed


def test_choice_result_prompt_injects_required_cast_authority_and_world_boundary() -> None:
    prompt = get_result_generation_prompt(
        event_description="林清刚结束需求评审，陆昊然在会议室门口等她复盘。",
        chosen_option="和陆昊然复盘需求优先级",
        effects={"knowledge": 5, "relationships": {"陆昊然": 3}},
        language="zh",
        character_settings=_modern_product_manager_settings(),
    )

    assert "预设关键人物" in prompt
    assert "陆昊然" in prompt
    assert "导师" in prompt
    assert "陈晓雨" in prompt
    assert "林一凡" in prompt
    assert "不得改名" in prompt
    assert "不得替换" in prompt
    assert "至少使用1位预设关键人物" in prompt
    assert "陆昊然、陈晓雨、林一凡至少一位" in prompt
    assert "现实主义世界边界" in prompt
    assert "禁止赛博朋克" in prompt
    assert "夜之城" in prompt
    assert "荒坂集团" in prompt


def test_custom_choice_result_prompt_injects_required_cast_authority_and_world_boundary() -> None:
    from config.prompts.story_prompts import get_custom_choice_result_prompt

    prompt = get_custom_choice_result_prompt(
        character_settings=_modern_product_manager_settings(),
        current_state=_player_state(),
        language="zh",
    )

    assert "预设关键人物" in prompt
    assert "陆昊然" in prompt
    assert "导师" in prompt
    assert "陈晓雨" in prompt
    assert "林一凡" in prompt
    assert "不得改名" in prompt
    assert "不得替换" in prompt
    assert "至少使用1位预设关键人物" in prompt
    assert "现实主义世界边界" in prompt
    assert "禁止赛博朋克" in prompt
    assert "夜之城" in prompt
    assert "荒坂集团" in prompt


def test_custom_choice_json_result_retries_when_story_violates_required_cast() -> None:
    from unittest.mock import Mock

    from src.game.story_service import StoryService

    ai = Mock()
    ai.generate_completion_json.side_effect = [
        {
            "story_continuation": (
                "苏婉清以投资人兼导师的身份接管了林清的产品复盘，"
                "陪她拆解路线并决定下一步融资节奏。陈晓雨和林一凡没有参与。"
            ),
            "effects": {"knowledge": 3},
        },
        {
            "story_continuation": (
                "林清决定按自己的方式复盘用户反馈。陆昊然在会议室白板前提醒她先确认需求优先级，"
                "陈晓雨帮她整理访谈记录，林一凡则把同期项目的数据对照表发了过来。"
            ),
            "effects": {"knowledge": 5, "relationships": {"陆昊然": 2}},
        },
    ]

    result = StoryService(ai_generator=ai, language="zh").generate_custom_choice_result(
        event_description="林清刚结束需求评审，陆昊然在会议室门口等她复盘。",
        custom_text="我想自己重新整理用户反馈。",
        character_settings=_modern_product_manager_settings(),
        current_state=_player_state(),
    )

    assert ai.generate_completion_json.call_count == 2
    assert "陆昊然" in result["story_continuation"]
    assert "苏婉清" not in result["story_continuation"]


def test_scheduled_event_prompt_inherits_story_authority_constraints() -> None:
    generator = RoundEventGenerator(
        player_state_getter=lambda: None,
        ai_generator=None,
        language_getter=lambda: "zh",
        character_introduction_service=None,
        summary_selector=None,
        relationship_service=None,
    )

    prompt = generator._build_scheduled_event_prompt(
        scheduled_events=[
            {
                "description": "周三和导师复盘需求优先级",
                "parties": ["陆昊然"],
                "event_hint": "围绕产品经理成长线推进",
            }
        ],
        player_state={
            "player_name": "林清",
            "week": 1,
            "current_round": 1,
        },
        character_settings=_modern_product_manager_settings(),
        language="zh",
    )

    assert "主角名称是：林清" in prompt
    assert "预设关键人物" in prompt
    assert "陆昊然" in prompt
    assert "陈晓雨" in prompt
    assert "林一凡" in prompt
    assert "不得改名" in prompt
    assert "不得替换" in prompt
    assert "至少使用1位预设关键人物" in prompt
    assert "陆昊然、陈晓雨、林一凡至少一位" in prompt
    assert "现实主义世界边界" in prompt
    assert "禁止赛博朋克" in prompt


def test_scheduled_event_prompt_uses_modern_timeline_title_constraints() -> None:
    """预定事件路径也必须沿用现代时间线标题，不能回退到原始 week 或章回体。"""
    generator = RoundEventGenerator(
        player_state_getter=lambda: None,
        ai_generator=None,
        language_getter=lambda: "zh",
        character_introduction_service=None,
        summary_selector=None,
        relationship_service=None,
    )

    prompt = generator._build_scheduled_event_prompt(
        scheduled_events=[
            {
                "description": "周一和导师复盘需求优先级",
                "parties": ["陆昊然"],
                "event_hint": "围绕产品经理成长线推进",
            }
        ],
        player_state={
            "player_name": "林清",
            "week": 2,
            "current_round": 0,
        },
        character_settings={
            "basic": {"name": "林清", "age": 28},
            "career": {"job_title": "产品经理", "company": "创业公司"},
            "wealth": {"currency": "¥", "currency_name": "元"},
        },
        language="zh",
    )

    assert "第3周·周一" in prompt
    assert "第2周，周一" not in prompt
    assert "时间线标题约束" in prompt
    assert "禁止使用章回体" in prompt
    assert "7字对仗标题" not in prompt
    assert "故事开头必须使用\"第" not in prompt


def test_scheduled_event_generation_retries_when_story_replaces_preset_cast() -> None:
    class DriftClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def call(self, **kwargs: Any) -> str:
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return """
                {
                  "event_description": "马老板把欠条摊在会议桌上，方蕾要求林清立刻接手苏州贸易公司的债务。",
                  "options": [
                    {"text": "先稳住马老板", "effects": {"mood": -5}},
                    {"text": "找方蕾谈判", "effects": {"knowledge": 3}}
                  ]
                }
                """
            return """
            {
              "event_description": "陆昊然把需求复盘表推到林清面前，提醒她先确认用户反馈，陈晓雨则陪她整理情绪。",
              "options": [
                {"text": "和陆昊然复盘需求", "effects": {"knowledge": 5}},
                {"text": "请陈晓雨陪同复盘", "effects": {"mood": 3}}
              ]
            }
            """

    class PlayerState:
        def to_dict(self) -> dict[str, Any]:
            return {
                "player_name": "林清",
                "week": 1,
                "current_round": 1,
                "character_settings": _modern_product_manager_settings(),
            }

    client = DriftClient()
    generator = RoundEventGenerator(
        player_state_getter=lambda: None,
        ai_generator=SimpleNamespace(ai_client=client),
        language_getter=lambda: "zh",
        character_introduction_service=None,
        summary_selector=None,
        relationship_service=None,
    )

    event = generator._generate_scheduled_event(
        scheduled_events=[
            {
                "description": "周三和导师复盘需求优先级",
                "parties": ["陆昊然"],
                "event_hint": "围绕产品经理成长线推进",
            }
        ],
        player_state=PlayerState(),
    )

    assert len(client.calls) == 2
    assert all(call["thinking"] is False for call in client.calls)
    assert event is not None
    assert "没有使用预设关键人物" in client.calls[1]["user_prompt"]
    assert "陆昊然" in event.event_description
    assert "马老板" not in event.event_description


def test_resume_existing_round_story_rejects_preset_cast_drift_before_options_only() -> None:
    drift_story = (
        "马老板把欠条摊在会议桌上，方蕾要求林清立刻接手苏州贸易公司的债务。"
        "赵子豪在旁边翻出旧账，王丽华不断催促她签字，整个故事完全围绕债务谈判展开。"
        "这段内容没有导师复盘、闺蜜支持或同期产品经理成长，只剩下陌生债主网络反复施压。"
    )
    repaired_event = GameEvent(
        event_description="陆昊然把需求复盘表推到林清面前，陈晓雨陪她整理情绪。",
        options=[
            EventOption(text="和陆昊然复盘需求", effects={"knowledge": 5}),
            EventOption(text="请陈晓雨陪同整理反馈", effects={"mood": 3}),
        ],
    )

    class FakeAI:
        def __init__(self) -> None:
            self.options_only_calls = 0
            self.round_generation_calls = 0

        def generate_options_only(self, **kwargs: Any) -> GameEvent:
            self.options_only_calls += 1
            return GameEvent(
                event_description=kwargs["story_description"],
                options=[
                    EventOption(text="继续债务谈判", effects={"mood": -5}),
                    EventOption(text="联系方蕾处理欠条", effects={"knowledge": 2}),
                ],
            )

        def generate_round_event(self, **kwargs: Any) -> GameEvent:
            self.round_generation_calls += 1
            return repaired_event

    class PlayerState:
        player_name = "林清"
        week = 1
        current_round = 1
        last_round_full_story = ""
        current_event_data: dict[str, Any] = {}
        pending_storylines: list[Any] = []
        established_facts: list[Any] = []
        last_event_concluded = True
        character_habits: list[Any] = []
        foreshadowing_seeds: list[Any] = []
        round_history = [
            {
                "week": 1,
                "round": 1,
                "event_description": drift_story,
                "story_continuation": "",
            }
        ]
        character_settings = _modern_product_manager_settings()

        def to_dict(self) -> dict[str, Any]:
            return {
                "player_name": "林清",
                "week": self.week,
                "current_round": self.current_round,
                "character_settings": self.character_settings,
                "round_history": self.round_history,
            }

        def get_pending_scheduled_events(self, *_args: Any) -> list[Any]:
            return []

        def get_round_context(self) -> str:
            return "上一轮生成的故事疑似漂移。"

        def get_game_date_info(self) -> dict[str, Any]:
            return {}

    fake_ai = FakeAI()
    generator = RoundEventGenerator(
        player_state_getter=PlayerState,
        ai_generator=fake_ai,
        language_getter=lambda: "zh",
        character_introduction_service=SimpleNamespace(
            maybe_generate_new_character=lambda probability=0.0: None,
            check_introduction_opportunity=lambda: None,
        ),
        summary_selector=SimpleNamespace(
            select_relevant_historical_summary=lambda _player_state: (None, None)
        ),
        relationship_service=SimpleNamespace(
            get_triggered_events=lambda *_args, **_kwargs: [],
            mark_event_triggered=lambda *_args, **_kwargs: None,
        ),
    )

    event = generator.generate_round_event()

    assert fake_ai.options_only_calls == 0
    assert fake_ai.round_generation_calls == 1
    assert event.event_description == repaired_event.event_description
    assert "马老板" not in event.event_description


def test_round_generation_failure_preserves_character_authority_by_not_persisting_fake_event() -> None:
    """A provider failure must not turn preset facts into a fallback story."""

    class FailingAI:
        def generate_round_event(self, **_kwargs: Any) -> GameEvent:
            raise RuntimeError("upstream model unavailable")

    class PlayerState:
        player_name = "林清"
        week = 2
        current_round = 0
        last_round_full_story = ""
        current_event_data: dict[str, Any] | None = None
        pending_storylines: list[Any] = []
        established_facts: list[Any] = []
        last_event_concluded = True
        character_habits: list[Any] = []
        foreshadowing_seeds: list[Any] = []
        round_history: list[Any] = []
        character_settings = _modern_product_manager_settings()

        def to_dict(self) -> dict[str, Any]:
            return {
                "player_name": self.player_name,
                "week": self.week,
                "current_round": self.current_round,
                "character_settings": self.character_settings,
            }

        def get_pending_scheduled_events(self, *_args: Any) -> list[Any]:
            return []

        def get_round_context(self) -> str:
            return "上一轮你开始适应产品经理工作。"

        def get_game_date_info(self) -> dict[str, Any]:
            return {}

    player_state = PlayerState()
    generator = RoundEventGenerator(
        player_state_getter=lambda: player_state,
        ai_generator=FailingAI(),
        language_getter=lambda: "zh",
        character_introduction_service=SimpleNamespace(
            maybe_generate_new_character=lambda probability=0.0: None,
            check_introduction_opportunity=lambda: None,
        ),
        summary_selector=SimpleNamespace(
            select_relevant_historical_summary=lambda _player_state: (None, None)
        ),
        relationship_service=SimpleNamespace(
            get_triggered_events=lambda *_args, **_kwargs: [],
            mark_event_triggered=lambda *_args, **_kwargs: None,
        ),
    )

    with pytest.raises(StoryGenerationFailure, match="upstream model unavailable"):
        generator.generate_round_event()

    assert player_state.current_event_data is None


def test_world_model_constraints_include_required_cast_from_character_settings() -> None:
    player_state = SimpleNamespace(
        week=2,
        player_name="林清",
        character_settings=_modern_product_manager_settings(),
        world_model_data={},
        established_facts=[],
    )

    text = WorldModel.from_player_state(player_state).build_constraints_text("zh")

    assert "预设关键人物" in text
    assert "陆昊然" in text
    assert "导师" in text
    assert "陈晓雨" in text
    assert "闺蜜" in text
    assert "林一凡" in text
    assert "同期" in text
    assert "不得改名" in text
    assert "不得替换" in text
    assert "至少使用1位预设关键人物" in text
    assert "陆昊然、陈晓雨、林一凡至少一位" in text
