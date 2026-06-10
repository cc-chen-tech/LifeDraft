"""Contract tests for preset relationship authority in story generation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from config.prompts.story_prompts import (
    get_result_generation_prompt,
    get_round_event_prompt,
    get_story_only_prompt,
)
from src.ai.models import EventOption, GameEvent
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
