"""Contract tests for preset relationship authority in story generation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from config.prompts.story_prompts import get_round_event_prompt, get_story_only_prompt
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
    assert "现实主义世界边界" in prompt
    assert "禁止赛博朋克" in prompt


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
