"""Contracts for keeping economic narrative without authoritative money state."""

from config.prompts.validation_prompts import get_story_analysis_prompt
from src.ai.story_analyzer import StoryAnalyzer
from src.utils.financial_narrative import (
    contains_precise_financial_fact,
    contains_tracked_wealth_state,
)


def test_financial_boundary_keeps_qualitative_economics() -> None:
    for precise in (
        "奖金到账5000元",
        "账户余额达到50000",
        "the account balance is USD 8,000",
    ):
        assert contains_precise_financial_fact(precise)

    for qualitative in (
        "收入连续3个月下降，经济压力加剧",
        "她因贫富差距而调整消费习惯",
        "the family faces more economic pressure",
    ):
        assert not contains_precise_financial_fact(qualitative)

    assert contains_tracked_wealth_state("当前财富值有所提升")
    assert contains_tracked_wealth_state("账户余额达到50000元")
    assert not contains_tracked_wealth_state("收入改善但消费更加谨慎")


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
