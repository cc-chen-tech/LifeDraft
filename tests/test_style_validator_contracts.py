from src.ai.narrative.style_manifest import (
    ChapterRules,
    LanguageConfig,
    PhilosophyConfig,
    StructureConfig,
    StyleManifest,
    TechniqueConfig,
)
from src.ai.narrative.style_validator import StyleAwareValidator


def _style() -> StyleManifest:
    return StyleManifest(
        philosophy=PhilosophyConfig(narrative_voice="第三人称"),
        structure=StructureConfig(
            macro="三幕式",
            arc="起承转合",
            chapter_rules=ChapterRules(
                opening_style="环境描写",
                closing_style="悬念",
                hook_types=["悬念"],
                avg_length="1000",
            ),
        ),
        techniques=TechniqueConfig(
            core_techniques=["意识流", "留白"],
            stylistic_devices=["对比"],
            narrative_patterns=["渐进式"],
        ),
        language=LanguageConfig(
            prose_style="简练",
            dialogue="克制",
            rhetoric=["比喻", "反问"],
            emotional_expression="内敛",
        ),
    )


def test_configured_style_returns_four_dimension_evidence_and_passing_score():
    validator = StyleAwareValidator(_style())
    story = (
        "清晨的雨如同薄雾，旅人走进城门。\n"
        "然而他想到旧日誓言，思绪渐渐清晰。\n"
        "「我怎能退缩？」他低声说道。\n"
        "终于，他决定穿过危机；沉默之后，谁知城外还有伏兵。"
    )

    passed, score, details = validator.validate(story)

    assert passed is True
    assert 0.3 <= score <= 1.0
    assert set(details["dimension_scores"]) == {"structure", "pacing", "language", "technique"}
    assert validator.validate_style_structure(story, {})[2]["macro"] == "三幕式"
    assert validator.validate_style_pacing(story, {})[2]["hook_detected"] is True
    assert validator.validate_style_language(story, {})[2]["rhetoric_found"] == ["比喻", "反问"]
    assert validator.validate_style_technique(story, {})[2]["technique_evidence"]["意识流"] is True


def test_missing_hook_is_a_pacing_failure_with_expected_evidence():
    validator = StyleAwareValidator(_style())

    passed, evidence, details = validator.validate_style_pacing("清晨，旅人平静回家。", {})

    assert passed is False
    assert "结尾未检测到预期的悬念钩子类型" in evidence
    assert details["hook_types"] == ["悬念"]
    assert details["hook_detected"] is False


def test_validator_helpers_weights_harness_and_no_style_fallback_are_deterministic():
    validator = StyleAwareValidator(_style(), weights={
        "structure": 1.0,
        "pacing": 0.0,
        "language": 0.0,
        "technique": 0.0,
    })

    assert validator._get_structure_indicators("英雄之旅") == ["召唤", "冒险", "试炼", "考验", "归来", "蜕变"]
    assert validator._get_arc_indicators("螺旋上升") == ["重复", "深化", "升华"]
    assert validator._get_opening_indicators("动作开场") == ["奔", "跑", "冲", "挥", "踏", "跃"]
    assert validator._get_closing_indicators("留白结尾") == ["……", "沉默", "无言", "不语"]
    assert validator._check_hook_presence("他却沉默了。", ["悬念"]) is True
    assert validator._check_rhetoric("风悄悄吹着，如同旧梦。", ["拟人", "比喻"]) == ["拟人", "比喻"]
    assert validator._analyze_prose_style("短句。更短！") == {
        "sentence_count": 2,
        "avg_sentence_length": 2.0,
        "max_sentence_length": 2,
        "min_sentence_length": 2,
    }
    assert validator._check_techniques("他想到往事，保持沉默……", ["意识流", "留白"]) == {
        "意识流": True,
        "留白": True,
    }
    assert validator._check_stylistic_devices("他们截然不同。", ["对比"]) == {"对比": True}
    assert validator._check_narrative_patterns("他渐渐明白。", ["渐进式"]) == {"渐进式": True}
    assert validator.get_weights()["structure"] == 1.0
    assert validator.get_overall_score("清晨，危机。") == validator.get_dimension_scores("清晨，危机。")["structure"]

    no_style = StyleAwareValidator()
    assert no_style.validate("任何文本") == (True, 1.0, {"skipped": True, "reason": "no style configured"})
    assert no_style.get_dimension_scores("任何文本") == {
        "structure": 1.0,
        "pacing": 1.0,
        "language": 1.0,
        "technique": 1.0,
    }
    assert no_style.as_harness_validator()("任何文本", {}) == (
        True,
        "",
        {"skipped": True, "reason": "no style configured"},
    )
