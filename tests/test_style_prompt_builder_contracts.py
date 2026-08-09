from src.ai.narrative.style_manifest import (
    ChapterRules,
    GlobalParameters,
    LanguageConfig,
    PhilosophyConfig,
    StructureConfig,
    StyleManifest,
    TechniqueConfig,
)
from src.ai.narrative.style_prompt_builder import StyleAwarePromptBuilder


def _complete_style() -> StyleManifest:
    return StyleManifest(
        style_id="wuxia",
        style_name="江湖写意",
        philosophy=PhilosophyConfig(
            narrative_voice="有限第三人称",
            thematic_core=["选择", "代价"],
            worldview="克制而险峻",
        ),
        structure=StructureConfig(
            macro="三幕式",
            arc="由误解走向担当",
            chapter_rules=ChapterRules(
                opening_style="危机切入",
                closing_style="余波未平",
                hook_types=["悬念", "反转"],
            ),
        ),
        techniques=TechniqueConfig(
            core_techniques=["白描", "留白"],
            stylistic_devices=["比喻"],
            narrative_patterns=["双线并进"],
        ),
        language=LanguageConfig(
            prose_style="简练",
            dialogue="含蓄",
            rhetoric=["对照"],
            emotional_expression="节制",
        ),
        global_parameters=GlobalParameters(
            temperature=0.61,
            temperature_schedule={"climax": 0.92},
        ),
    )


def test_complete_style_builds_hard_soft_and_temperature_guidance():
    prompt = StyleAwarePromptBuilder(_complete_style()).build()

    assert "[MUST] 叙事视角: 采用有限第三人称进行叙述" in prompt
    assert "[MUST] 主题内核: 围绕「选择、代价」展开叙事" in prompt
    assert "[SHOULD] 核心技法: 运用白描、留白等叙事技法" in prompt
    assert "[SHOULD] 情感表达: 节制" in prompt
    assert "[创作参数] temperature=0.61" in prompt


def test_style_chapter_guidance_and_scene_temperature_follow_manifest():
    builder = StyleAwarePromptBuilder(_complete_style())

    assert builder.build_chapter_opening("主角失去旧友") == (
        "[章节开头指引] 本章开头应采用「危机切入」的方式展开。\n"
        "上一章概要: 主角失去旧友\n"
        "请在承接上文的基础上，以指定的开头风格自然过渡。"
    )
    assert builder.build_chapter_ending_hint() == (
        "[章节结尾指引] 结尾应设置悬念钩子，可选类型: 悬念、反转。\n"
        "结尾风格要求: 余波未平"
    )
    assert builder.get_scene_temperature("climax") == 0.92
    assert builder.get_scene_temperature("quiet") == 0.61


def test_sparse_and_missing_styles_keep_optional_guidance_safe():
    sparse_builder = StyleAwarePromptBuilder(StyleManifest())
    missing_builder = StyleAwarePromptBuilder(None)

    assert sparse_builder.build_style_hard_constraints() == ""
    assert sparse_builder.build_style_soft_suggestions() == ""
    assert sparse_builder.build_chapter_opening() == ""
    assert sparse_builder.build_chapter_ending_hint() == ""
    assert missing_builder.build() == ""
    assert missing_builder.build_chapter_opening() == ""
    assert missing_builder.build_chapter_ending_hint() == ""
    assert missing_builder.get_scene_temperature() == 0.85


def test_positive_token_budget_truncates_complete_style_prompt_deterministically():
    prompt = StyleAwarePromptBuilder(_complete_style(), max_tokens=6).build()

    assert len(prompt) == 12
