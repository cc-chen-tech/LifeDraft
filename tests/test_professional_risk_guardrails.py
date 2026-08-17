"""Regression coverage for unsafe professional-risk guarantees in generated text."""

from unittest.mock import MagicMock

from src.ai.professional_risk import (
    apply_professional_risk_guardrail,
    find_unsafe_professional_claims,
)
from src.ai.quick_validator import quick_validate_story
from src.ai.summary_generator import SummaryGenerator
from src.ai.system_prompts import get_system_prompt
from src.ai.text_quality import normalize_generated_story
from src.game.weekly_summary import WeeklySummaryGenerator
import pytest

pytestmark = [pytest.mark.unit]


UNSAFE_LEGAL_ZH = (
    "律师建议你用母亲名义注册公司来规避竞业限制，称这是合法合规的路径，"
    "风险几乎为零。"
)


def test_detects_and_rewrites_relative_name_noncompete_zero_risk_claim() -> None:
    assert find_unsafe_professional_claims(UNSAFE_LEGAL_ZH, language="zh")

    guarded = apply_professional_risk_guardrail(UNSAFE_LEGAL_ZH, language="zh")

    assert "风险几乎为零" not in guarded
    assert "合法合规的路径" not in guarded
    assert "实际控制" in guarded
    assert "有资质的法律专业人士" in guarded


def test_rewrites_medical_absolute_safety_claim_with_clinician_caution() -> None:
    unsafe = "医生说这种治疗绝对安全，保证不会有任何风险。"

    guarded = apply_professional_risk_guardrail(unsafe, language="zh")

    assert "绝对安全" not in guarded
    assert "保证不会有任何风险" not in guarded
    assert "个体" in guarded
    assert "有资质的医疗专业人士" in guarded


def test_rewrites_english_legal_guarantee() -> None:
    unsafe = (
        "The lawyer called using a relative's name a compliant path with zero risk."
    )

    guarded = apply_professional_risk_guardrail(unsafe, language="en")

    assert "zero risk" not in guarded.lower()
    assert "qualified legal professional" in guarded.lower()


def test_guardrail_does_not_change_uncertain_legal_fiction_or_unrelated_safety() -> (
    None
):
    uncertain = "律师翻开案卷，提醒你结果仍不确定，需要结合证据判断。"
    unrelated = "暴雨来临前，他们躲进了绝对安全的山洞。"

    assert apply_professional_risk_guardrail(uncertain, language="zh") == uncertain
    assert apply_professional_risk_guardrail(unrelated, language="zh") == unrelated


def test_guardrail_is_idempotent() -> None:
    once = apply_professional_risk_guardrail(UNSAFE_LEGAL_ZH, language="zh")
    assert apply_professional_risk_guardrail(once, language="zh") == once


def test_quick_validator_rejects_raw_professional_guarantee() -> None:
    result = quick_validate_story(UNSAFE_LEGAL_ZH, language="zh")

    assert result.passed is False
    assert "unsafe_professional_guarantee" in result.issues


def test_story_normalizer_applies_professional_guardrail() -> None:
    guarded = normalize_generated_story(UNSAFE_LEGAL_ZH, language="zh")

    assert not find_unsafe_professional_claims(guarded, language="zh")
    assert "有资质的法律专业人士" in guarded


def test_story_and_summary_prompts_forbid_professional_guarantees() -> None:
    for key in (
        "story_novelist",
        "story_continuation",
        "story_rewriter",
        "story_compressor",
        "weekly_summary",
        "four_week_summary",
        "yearly_summary",
        "narrative_summary",
    ):
        zh_prompt = get_system_prompt(key, "zh")
        en_prompt = get_system_prompt(key, "en")
        assert "零风险" in zh_prompt
        assert "有资质的专业人士" in zh_prompt
        assert "zero-risk" in en_prompt.lower()
        assert "qualified professional" in en_prompt.lower()


def test_summary_cleaner_applies_professional_guardrail() -> None:
    guarded = SummaryGenerator._clean_summary_text(UNSAFE_LEGAL_ZH)

    assert not find_unsafe_professional_claims(guarded, language="zh")


def test_weekly_summary_final_boundary_applies_professional_guardrail() -> None:
    ai_generator = MagicMock()
    ai_generator.generate_completion.return_value = UNSAFE_LEGAL_ZH
    generator = WeeklySummaryGenerator(ai_generator=ai_generator, language="zh")

    guarded = generator._generate_ai_summary(
        week=1,
        previous_state={},
        changes={"energy": 0, "mood": 0, "knowledge": 0, "wealth": 0},
        decisions=[],
        current_state=MagicMock(energy=80, mood=80, knowledge=80),
        language="zh",
    )

    assert not find_unsafe_professional_claims(guarded, language="zh")
