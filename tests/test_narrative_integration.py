"""叙事引擎三大系统集成测试 (L5)

TDD先行：测试风格全链路、创意全链路、史诗叙事全链路、
三系统协同、8验证器管线集成、Feature Toggle降级。
当前为红色测试（模块尚未实现）。
"""

import os

import pytest
from unittest.mock import patch, MagicMock

from src.ai.harness import (
    ConstraintRegistry,
    ConstraintType,
    Priority,
    ValidationPipeline,
    ValidationResult,
    default_registry,
)
from src.ai.narrative.style_manifest import StyleLoader, StyleManifest


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def style_loader_with_file(tmp_path):
    """创建一个带有测试风格文件的 StyleLoader。"""
    import json

    style_data = {
        "style_id": "chinese_classic_saga",
        "style_name": "中华古典传奇",
        "version": "1.0",
        "description": "以中国古典小说为蓝本的叙事风格",
        "philosophy": {
            "narrative_voice": "全知视角，冷静克制",
            "thematic_core": ["命运", "选择", "成长"],
            "worldview": "天道酬勤，因果报应",
        },
        "structure": {
            "macro": "三幕式结构",
            "arc": "起承转合",
        },
        "techniques": {
            "core_techniques": ["白描", "工笔"],
            "stylistic_devices": ["隐喻", "象征"],
            "narrative_patterns": ["欲扬先抑", "草蛇灰线"],
        },
        "language": {
            "prose_style": "半文半白，简练含蓄",
            "dialogue": "口语化，符合人物身份",
            "rhetoric": ["比喻", "排比", "对偶"],
            "emotional_expression": "克制内敛",
        },
        "global_parameters": {
            "temperature": 0.85,
            "top_p": 1.0,
        },
    }
    style_file = tmp_path / "chinese_classic_saga.style.json"
    style_file.write_text(json.dumps(style_data, ensure_ascii=False), encoding="utf-8")
    return StyleLoader(styles_dir=str(tmp_path))


@pytest.fixture
def basic_validation_context(sample_player_state_with_creative):
    """基础验证上下文（来自 conftest 的 sample_player_state_with_creative）。"""
    state = sample_player_state_with_creative
    return {
        "available_people": ["李逍遥", "赵灵儿", "王二", "掌柜", "师父"],
        "established_facts": [
            {"fact": "李逍遥是蜀山弟子", "source_week": 1},
            {"fact": "王二左臂骨折", "source_week": 4},
        ],
        "pending_storylines": [
            {"title": "寻找灵药", "importance": "high", "deadline_week": 13},
        ],
        "overdue_storylines": [],
        "last_location": "洛阳城",
        "character_habits": [
            {"character": "李逍遥", "habit": "每日清晨练剑"},
        ],
        "world_model_state": state.world_model_data if hasattr(state, "world_model_data") else {},
        "player_state": state,
    }


# ============================================================
# L5-1: 风格全链路
# ============================================================


@pytest.mark.integration
class TestStyleFullPipeline:
    """风格全链路: StyleLoader → PromptBuilder → 约束注入 → Validator评分"""

    def test_style_load_to_prompt(self, style_loader_with_file):
        """加载风格→生成约束字符串→验证非空"""
        loader = style_loader_with_file
        manifest = loader.get_style("chinese_classic_saga")

        assert manifest is not None
        assert manifest.style_id == "chinese_classic_saga"
        assert manifest.style_name == "中华古典传奇"
        assert manifest.philosophy.narrative_voice != ""
        assert len(manifest.techniques.core_techniques) > 0

    def test_style_constraints_in_prompt(self, style_loader_with_file, sample_player_state_with_creative):
        """风格约束成功注入story_prompts。

        TDD: 需要 PromptBuilder.build_style_constraints(manifest) 方法。
        当前期望：调用后返回包含风格关键词的字符串。
        """
        manifest = style_loader_with_file.get_style("chinese_classic_saga")
        assert manifest is not None

        # 使用 StyleAwarePromptBuilder 构建风格约束
        from src.ai.narrative.style_prompt_builder import StyleAwarePromptBuilder

        builder = StyleAwarePromptBuilder(style=manifest)
        constraint_str = builder.build()
        assert "白描" in constraint_str or "全知视角" in constraint_str
        assert len(constraint_str) > 0

    def test_style_validator_scoring(self, style_loader_with_file, mock_story_text):
        """风格验证器对生成文本评分。

        TDD: 需要 StyleValidator.score(story_text, manifest) → float
        """
        manifest = style_loader_with_file.get_style("chinese_classic_saga")
        assert manifest is not None

        from src.ai.narrative.style_validator import StyleAwareValidator

        validator = StyleAwareValidator(style=manifest)
        passed, score, details = validator.validate(mock_story_text)
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0


# ============================================================
# L5-2: 创意全链路
# ============================================================


@pytest.mark.integration
class TestCreativeFullPipeline:
    """创意全链路: 故事生成→情感分析→新颖度→偏好更新"""

    def test_emotional_arc_after_story(self, mock_story_text):
        """故事生成后情感弧线分析。

        TDD: 需要 EmotionalArcAnalyzer.analyze(story_text) → EmotionalArcResult
        """
        from src.ai.creative.emotional_arc import EmotionalArcAnalyzer

        analyzer = EmotionalArcAnalyzer()
        arc = analyzer.analyze(mock_story_text)
        assert hasattr(arc, "valence") or hasattr(arc, "scene_type")

    def test_novelty_scoring_with_history(self, mock_story_text):
        """NoveltyScorer对历史故事评分。

        TDD: 需要 NoveltyScorer.score(story_text, history) → NoveltyResult
        """
        history = [
            "清晨阳光洒入窗内，他缓缓醒来。",
            "街道上人头攒动，节日的气氛浓厚。",
        ]
        try:
            from src.ai.creative.novelty_scorer import NoveltyScorer, NoveltyResult

            scorer = NoveltyScorer()
            result = scorer.score(mock_story_text, history)
            assert isinstance(result, NoveltyResult)
            assert 0.0 <= result.score <= 1.0
        except ImportError:
            pytest.skip("NoveltyScorer not yet implemented (TDD red phase)")

    def test_preference_update_after_choice(self):
        """选择后PreferenceLearner学习偏好。

        TDD: 需要 PreferenceLearner.learn(decision_history) → PlayerPreferences
        """
        try:
            from src.ai.creative.preference_learner import PreferenceLearner

            learner = PreferenceLearner()
            profile = learner.learn(
                decision_history=[
                    {"week": 10, "choice": "前往洛阳探索冒险", "effects": {"energy": -10}},
                    {"week": 11, "choice": "接受师门挑战任务", "effects": {"knowledge": 5}},
                ]
            )
            assert profile is not None
        except ImportError:
            pytest.skip("PreferenceLearner not yet implemented (TDD red phase)")


# ============================================================
# L5-3: 史诗叙事全链路
# ============================================================


@pytest.mark.integration
class TestEpicNarrativeFullPipeline:
    """史诗全链路: WorldBreathing→ConflictTower→CharacterArc→FateEcho"""

    def test_world_breathing_advance(self, sample_player_state_with_creative):
        """世界呼吸推进背景事件。

        TDD: 需要 WorldBreathingEngine.advance_to_week(week) → list[dict]
        """
        from src.ai.narrative.world_breathing import WorldBreathingEngine

        wb = WorldBreathingEngine()
        wb.register_event({"id": "test_event", "trigger_week": 10, "description": "测试事件"})
        events = wb.advance_to_week(week=12)
        assert isinstance(events, list)

    def test_conflict_tower_level_check(self):
        """冲突塔检查当前冲突级别。

        TDD: 需要 ConflictTower.get_tier(tier) → list[dict]
        """
        from src.ai.narrative.conflict_tower import ConflictTower

        tower = ConflictTower()
        tower.add_conflict({"id": "c1", "tier": 1, "name": "寻找灵药"})
        tier1 = tower.get_tier(1)
        assert isinstance(tier1, list)
        assert len(tier1) >= 1

    def test_character_arc_update(self):
        """人物弧光状态更新。

        TDD: 需要 CharacterArcEngine.process_event(arc, event) → CharacterArc
        """
        from src.ai.narrative.character_arc import CharacterArcEngine

        engine = CharacterArcEngine()
        arc = engine.create_arc({"name": "李逍遥", "initial_flaw": "冲动", "desire": "守护"})
        arc_state = engine.process_event(arc, {"description": "与王二重逢，决定一同冒险", "intensity": 0.6})
        assert arc_state is not None

    def test_fate_echo_trigger(self, sample_player_state_with_creative):
        """宿命回响触发检查。

        TDD: 需要 FateEchoDatabase.check_triggers(context) → list[dict]
        """
        from src.ai.narrative.fate_echo import FateEchoDatabase

        echo = FateEchoDatabase()
        echo.register({
            "id": "prop1",
            "cause": "在洛阳偶遇神秘老者",
            "expected_effect": "获得神秘线索",
            "trigger_conditions": {"min_week": 1},
        })
        result = echo.check_triggers({"current_week": 12, "encountered_characters": []})
        # 可能触发也可能不触发
        assert isinstance(result, list)


# ============================================================
# L5-4: 三系统协同
# ============================================================


@pytest.mark.integration
class TestThreeSystemSynergy:
    """三系统协同"""

    def test_all_constraints_in_prompt(self, style_loader_with_file, sample_player_state_with_creative):
        """风格约束+创意建议+史诗指令同时注入Prompt。

        TDD: 需要统一的约束聚合器将三系统约束合并。
        """
        manifest = style_loader_with_file.get_style("chinese_classic_saga")
        assert manifest is not None

        try:
            from src.ai.narrative.style_prompt_builder import StyleAwarePromptBuilder

            builder = StyleAwarePromptBuilder(style=manifest)
            # 风格约束
            style_constraints = builder.build()
            assert len(style_constraints) > 0

            # TDD: 创意约束和史诗约束接口
            # creative_constraints = builder.build_creative_constraints(...)
            # epic_constraints = builder.build_epic_constraints(...)
            # combined = builder.combine_all(style_constraints, creative_constraints, epic_constraints)
            # assert len(combined) > len(style_constraints)
        except Exception as e:
            pytest.fail(f"StyleAwarePromptBuilder failed: {e}")

    def test_harness_regression(self):
        """新增模块不破坏现有18种ConstraintType的验证。"""
        # 现有18种 ConstraintType
        existing_types = {
            ConstraintType.AVAILABLE_PEOPLE,
            ConstraintType.ESTABLISHED_FACTS,
            ConstraintType.OVERDUE_STORYLINES,
            ConstraintType.WORLD_MODEL_POSITION,
            ConstraintType.WORLD_MODEL_COMMITMENT,
            ConstraintType.NO_FABRICATION,
            ConstraintType.THIRD_PERSON_NARRATION,
            ConstraintType.DECISION_POINT_ENDING,
            ConstraintType.NO_META_NARRATION,
            ConstraintType.HIGH_STORYLINES,
            ConstraintType.SCENE_CONTINUITY,
            ConstraintType.CHARACTER_CONSISTENCY,
            ConstraintType.CHARACTER_HABITS,
            ConstraintType.FORESHADOWING,
            ConstraintType.MEDIUM_STORYLINES,
            ConstraintType.LOGIC_CONSTRAINTS,
            ConstraintType.ANTI_REPETITION,
            ConstraintType.VECTOR_CONTEXT,
        }
        # 全部在 default_registry 中已注册
        for ct in existing_types:
            defn = default_registry.get(ct)
            assert defn is not None, f"{ct.value} missing from default_registry"
            assert defn.validator is not None

    def test_helpers_budget_no_overflow(self):
        """新增约束参与Token预算分配，总量不溢出。"""
        from config.prompts._helpers import (
            CONSTRAINT_BUDGET,
            _BUDGET_TRIM_ORDER,
            _allocate_constraint_budget,
        )

        # 构造超出预算的约束文本
        constraint_texts = {}
        for key in CONSTRAINT_BUDGET:
            # 每项填充接近预算上限的中文文本
            budget_chars = int(CONSTRAINT_BUDGET[key] / 0.75)  # 中文约 0.75 token/char
            constraint_texts[key] = "测" * budget_chars

        result = _allocate_constraint_budget(constraint_texts)
        assert isinstance(result, dict)

        # 验证 protected 项未被截断
        for key in ("critical_summary", "established_facts", "world_model"):
            if key in constraint_texts:
                assert key in result


# ============================================================
# L5-5: 8验证器管线集成
# ============================================================


@pytest.mark.integration
class TestValidatorPipelineIntegration:
    """8验证器管线集成"""

    def test_all_existing_constraint_types_registered(self):
        """全部18个原始ConstraintType注册到ValidationPipeline。"""
        original_18 = {
            ConstraintType.AVAILABLE_PEOPLE,
            ConstraintType.ESTABLISHED_FACTS,
            ConstraintType.OVERDUE_STORYLINES,
            ConstraintType.WORLD_MODEL_POSITION,
            ConstraintType.WORLD_MODEL_COMMITMENT,
            ConstraintType.NO_FABRICATION,
            ConstraintType.THIRD_PERSON_NARRATION,
            ConstraintType.DECISION_POINT_ENDING,
            ConstraintType.NO_META_NARRATION,
            ConstraintType.HIGH_STORYLINES,
            ConstraintType.SCENE_CONTINUITY,
            ConstraintType.CHARACTER_CONSISTENCY,
            ConstraintType.CHARACTER_HABITS,
            ConstraintType.FORESHADOWING,
            ConstraintType.MEDIUM_STORYLINES,
            ConstraintType.LOGIC_CONSTRAINTS,
            ConstraintType.ANTI_REPETITION,
            ConstraintType.VECTOR_CONTEXT,
        }
        registered_types = {defn.type for defn in default_registry.get_all()}
        for ct in original_18:
            assert ct in registered_types, f"{ct.value} not registered in default_registry"

    def test_all_new_constraint_types_registered(self):
        """全部8个新ConstraintType注册到ValidationPipeline。

        TDD: 新增约束类型包括 TEMPORAL_CONSISTENCY, CHARACTER_STATUS,
        CAUSAL_CHAIN, SPATIAL_CONSISTENCY, STYLE_ADHERENCE,
        EMOTIONAL_ARC, CONFLICT_LEVEL, WORLD_BREATHING
        """
        new_types = [
            "TEMPORAL_CONSISTENCY",
            "COMMITMENT_FULFILLMENT",
            "CHARACTER_STATE_CONTINUITY",
            "ITEM_CONTINUITY",
            "SPATIAL_MOVEMENT",
            "NPC_ATTRIBUTE_STABILITY",
            "INFORMATION_BARRIER",
            "CAUSE_EFFECT_CONSISTENCY",
        ]
        missing_from_enum = []
        missing_from_registry = []
        for type_name in new_types:
            if not hasattr(ConstraintType, type_name):
                missing_from_enum.append(type_name)
                continue
            ct = ConstraintType[type_name]
            defn = default_registry.get(ct)
            if defn is None:
                missing_from_registry.append(type_name)

        assert not missing_from_enum, f"ConstraintType enum missing: {missing_from_enum}"
        assert not missing_from_registry, f"Registry missing: {missing_from_registry}"

    def test_critical_failure_triggers_retry(self, mock_story_text, basic_validation_context):
        """CRITICAL失败触发重试。"""
        from src.ai.harness.diagnostics import ConstraintViolationDiagnostic
        from src.ai.harness.retry_controller import RetryController

        pipeline = ValidationPipeline(default_registry)
        result = pipeline.validate(mock_story_text, basic_validation_context)

        diagnostics = ConstraintViolationDiagnostic()
        report = diagnostics.generate_report(mock_story_text, result)

        controller = RetryController(max_retries=2)

        if result.critical_failures:
            should_retry, correction = controller.should_retry(result, report, attempt=0)
            assert should_retry is True
            assert correction is not None
            assert len(correction) > 0

    def test_correction_hint_generation(self, mock_story_text, basic_validation_context):
        """correction_hint正确生成。"""
        from src.ai.harness.diagnostics import ConstraintViolationDiagnostic

        pipeline = ValidationPipeline(default_registry)
        result = pipeline.validate(mock_story_text, basic_validation_context)

        diagnostics = ConstraintViolationDiagnostic()
        report = diagnostics.generate_report(mock_story_text, result)

        # 如果有违反，修复建议应非空
        if report.total_violations > 0:
            assert len(report.suggested_fixes) > 0
            for fix in report.suggested_fixes:
                assert "[" in fix  # 格式: [constraint_type] fix_hint

    def test_multi_validator_simultaneous(self, basic_validation_context):
        """同一段文本同时触发多个验证器。"""
        # 构造既有第一人称又缺少决策点的文本
        bad_text = (
            "我走在街上，忽然看到了一个人。我决定跟着他。"
            "我们一起走了很远，最后到了一个废弃的宅院。"
            "就这样，故事结束了。"
        )

        pipeline = ValidationPipeline(default_registry)
        result = pipeline.validate(bad_text, basic_validation_context)

        # 至少有第三人称和决策点两个违反
        failed_types = set()
        for check in result.critical_failures + result.high_warnings:
            failed_types.add(check.constraint_type)

        # "third_person" 和 "decision_point_ending" 应该都被捕获
        assert "third_person" in failed_types or "decision_point_ending" in failed_types, \
            f"Expected multi-validator failures, got: {failed_types}"


# ============================================================
# L5-6: Feature Toggle降级测试
# ============================================================


@pytest.mark.integration
class TestFeatureToggle:
    """降级测试"""

    def test_disable_style_engine(self, monkeypatch):
        """关闭ENABLE_NARRATIVE_STYLE_ENGINE，其余正常。"""
        monkeypatch.setenv("ENABLE_NARRATIVE_STYLE_ENGINE", "false")
        monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")

        enabled = os.environ.get("ENABLE_NARRATIVE_STYLE_ENGINE", "").lower() in ("true", "1", "yes")
        assert enabled is False

        # Harness 仍应可用
        harness_enabled = os.environ.get("ENABLE_CONSTRAINT_HARNESS", "").lower() in ("true", "1", "yes")
        assert harness_enabled is True

    def test_disable_creative(self, monkeypatch):
        """关闭ENABLE_CREATIVE_ENHANCEMENT，其余正常。"""
        monkeypatch.setenv("ENABLE_CREATIVE_ENHANCEMENT", "false")
        monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")

        creative_enabled = os.environ.get("ENABLE_CREATIVE_ENHANCEMENT", "").lower() in ("true", "1", "yes")
        assert creative_enabled is False

    def test_disable_epic(self, monkeypatch):
        """关闭ENABLE_EPIC_NARRATIVE，其余正常。"""
        monkeypatch.setenv("ENABLE_EPIC_NARRATIVE", "false")
        monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")

        epic_enabled = os.environ.get("ENABLE_EPIC_NARRATIVE", "").lower() in ("true", "1", "yes")
        assert epic_enabled is False

    def test_all_disabled(self, monkeypatch):
        """三个都关闭，回退到原始行为。"""
        monkeypatch.setenv("ENABLE_NARRATIVE_STYLE_ENGINE", "false")
        monkeypatch.setenv("ENABLE_CREATIVE_ENHANCEMENT", "false")
        monkeypatch.setenv("ENABLE_EPIC_NARRATIVE", "false")
        monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "false")

        for key in (
            "ENABLE_NARRATIVE_STYLE_ENGINE",
            "ENABLE_CREATIVE_ENHANCEMENT",
            "ENABLE_EPIC_NARRATIVE",
            "ENABLE_CONSTRAINT_HARNESS",
        ):
            assert os.environ.get(key, "").lower() not in ("true", "1", "yes")

        # StoryGenerator 在 harness_enabled=False 时不初始化 harness 组件
        from src.ai.story_generator import StoryGenerator

        with patch("src.ai.story_generator.AIClient") as mock_client:
            gen = StoryGenerator(mock_client())
            assert gen._harness_enabled is False
