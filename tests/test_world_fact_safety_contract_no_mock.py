"""No-mock contracts for factual boundaries in generated world settings."""

from config.prompts.character_prompts import get_character_setting_prompt
from src.game.world_fact_safety import qualify_generated_world_facts
import pytest

pytestmark = [pytest.mark.unit]



PRECISE_WORLD = {
    "world_description": (
        "项目必须取得数据隐私保护认证（DSR），并完成市级教育评估备案。"
    ),
    "technology_level": "认证和备案流程固定需要4-6个月。",
    "social_system": "当地GDP增长5.2%，因此审批会收紧。",
    "economy": "风险投资额同比下降40%。",
}


def test_world_prompt_forbids_unsupported_real_sounding_facts() -> None:
    prompt = get_character_setting_prompt(
        setting_type="world",
        player_name="林晓",
        life_vision="2026年现实主义教育科技产品经理成长",
        previous_settings={"era": {"year": 2026, "era_description": "当代中国"}},
        language="zh",
        feedback="补充具体合规约束",
    )

    assert "不得虚构" in prompt
    assert "法规" in prompt
    assert "认证" in prompt
    assert "统计" in prompt
    assert "故事设定假设" in prompt
    assert "不构成现实法律、合规或经济建议" in prompt


def test_precise_generated_world_claims_are_visibly_qualified_and_idempotent() -> None:
    qualified = qualify_generated_world_facts(PRECISE_WORLD, language="zh")

    for field in PRECISE_WORLD:
        assert qualified[field].startswith("故事设定假设，不代表现实法规或统计：")

    assert qualify_generated_world_facts(qualified, language="zh") == qualified


def test_qualitative_world_description_remains_unchanged() -> None:
    qualitative = {
        "world_description": "当代城市中的教育科技团队重视用户隐私与稳健增长。",
        "technology_level": "使用成熟的互联网和人工智能辅助工具。",
        "social_system": "遵循现实社会的一般制度。",
        "economy": "市场竞争谨慎，创业团队控制成本。",
    }

    assert qualify_generated_world_facts(qualitative, language="zh") == qualitative

