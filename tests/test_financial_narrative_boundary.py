"""Contracts for keeping economic narrative without authoritative money state."""

import json
from types import SimpleNamespace

import pytest

from config.prompts.validation_prompts import get_story_analysis_prompt
from src.ai.story_analyzer import DynamicFact, StoryAnalyzer
from src.game.assistant_grounding import AssistantEvidence
from src.game.world_model import WorldModel
from src.utils.financial_narrative import (
    contains_precise_financial_fact,
    contains_tracked_wealth_state,
)


@pytest.mark.parametrize(
    "text",
    (
        "奖金到账5000元",
        "账户余额达到50000",
        "USD 8,000",
        "RMB 5000",
        "8,000 USD",
    ),
)
def test_precise_money_formats_are_classified(text: str) -> None:
    assert contains_precise_financial_fact(text)


@pytest.mark.parametrize(
    "text",
    (
        "当前财富值有所提升",
        "账户余额有所改善",
        "存款继续增长",
    ),
)
def test_unnumbered_tracked_money_state_is_classified(text: str) -> None:
    assert contains_tracked_wealth_state(text)


@pytest.mark.parametrize(
    "text",
    (
        "财富并非人生目标，她一直重视家人",
        "收入连续3个月下降，经济压力加剧",
        "她因贫富差距而调整消费习惯",
        "the family faces more economic pressure",
    ),
)
def test_qualitative_economic_or_value_statements_are_preserved(text: str) -> None:
    assert not contains_precise_financial_fact(text)
    assert not contains_tracked_wealth_state(text)


def test_prompt_forbids_exact_financial_authority() -> None:
    prompts = [
        get_story_analysis_prompt("故事", "选择", "", {}, 1, language)
        for language in ("zh", "en")
    ]

    assert "精确金额" in prompts[0]
    assert "定性" in prompts[0]
    assert "exact monetary" in prompts[1].lower()
    assert "qualitative" in prompts[1].lower()
    assert "拿到奖金" not in prompts[0]
    assert "received bonus" not in prompts[1]


def test_story_analyzer_filters_exact_money_fact() -> None:
    analyzer = StoryAnalyzer(client=None)
    response = """{
      "facts": [
        {
          "action": "new",
          "fact_type": "financial",
          "subject": "林岚",
          "description": "公司发放了5000元奖金",
          "constraint_text": "后续必须保持账户余额增加5000元",
          "source_excerpt": "奖金到账5000元"
        },
        {
          "action": "new",
          "fact_type": "financial",
          "subject": "林岚",
          "description": "家庭经济压力加剧",
          "constraint_text": "经济压力会影响她的消费选择",
          "source_excerpt": "家庭经济压力加剧"
        }
      ]
    }"""

    facts = analyzer._parse_analysis_response(response, 4, [], "hash")

    assert [fact.description for fact in facts] == ["家庭经济压力加剧"]


@pytest.mark.parametrize(
    "unsafe_fact",
    ("USD 8,000", "RMB 5000", "当前财富值有所提升", "存款继续增长"),
)
def test_story_analyzer_filters_authoritative_money_state(unsafe_fact: str) -> None:
    analyzer = StoryAnalyzer(client=None)
    response = json.dumps(
        {
            "facts": [
                {
                    "action": "new",
                    "fact_type": "economic_context",
                    "subject": "林岚",
                    "description": unsafe_fact,
                    "constraint_text": f"后续必须保持：{unsafe_fact}",
                    "source_excerpt": unsafe_fact,
                },
                {
                    "action": "new",
                    "fact_type": "value",
                    "subject": "林岚",
                    "description": "财富并非人生目标，她一直重视家人",
                    "constraint_text": "她做决定时仍会优先考虑家人",
                    "source_excerpt": "她一直重视家人",
                },
            ]
        },
        ensure_ascii=False,
    )

    facts = analyzer._parse_analysis_response(response, 4, [], "hash")

    assert [fact.description for fact in facts] == ["财富并非人生目标，她一直重视家人"]


@pytest.mark.parametrize(
    "unsafe_fact",
    ("USD 8,000", "RMB 5000", "当前财富值有所提升", "账户余额有所改善"),
)
def test_world_model_filters_authoritative_money_state(unsafe_fact: str) -> None:
    model = WorldModel()
    model.dynamic_facts = [
        DynamicFact(
            fact_id="unsafe",
            fact_type="economic_context",
            subject="林岚",
            description=unsafe_fact,
            constraint_text=f"后续必须保持：{unsafe_fact}",
        ),
        DynamicFact(
            fact_id="safe",
            fact_type="value",
            subject="林岚",
            description="财富并非人生目标，她一直重视家人",
            constraint_text="她做决定时仍会优先考虑家人",
        ),
    ]

    constraints = model.build_constraints_text("zh")

    assert unsafe_fact not in constraints
    assert "优先考虑家人" in constraints
    assert [fact["fact_id"] for fact in model.to_dict()["dynamic_facts"]] == ["safe"]


@pytest.mark.parametrize(
    "unsafe_fact",
    ("USD 8,000", "RMB 5000", "当前财富值有所提升", "存款继续增长"),
)
def test_assistant_filters_authoritative_money_state(unsafe_fact: str) -> None:
    player = SimpleNamespace(
        character_settings={},
        life_vision="",
        continuity_ledger={
            "mutable_states": {
                "facts": {
                    "unsafe": {
                        "subject": "林岚",
                        "category": "economic_context",
                        "fact": unsafe_fact,
                        "source_event_id": "w1-r1",
                    },
                    "safe": {
                        "subject": "林岚",
                        "category": "value",
                        "fact": "财富并非人生目标，她一直重视家人",
                        "source_event_id": "w1-r2",
                    },
                }
            }
        },
    )

    evidence = AssistantEvidence.from_player_state(player)

    assert "state:unsafe" not in evidence.records
    assert evidence.records["state:safe"].fact == "财富并非人生目标，她一直重视家人"
