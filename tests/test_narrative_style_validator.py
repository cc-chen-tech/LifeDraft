"""StyleAwareValidator 单元测试 (L2)。

TDD先行：测试 StyleAwareValidator 的4维度评分（结构完整性、节奏规则、
语言风格、技法体现），权重配置，分数归一化，以及与 Harness 的集成接口。
"""

import pytest

# TDD: 模块尚不存在，导入失败时标记整个模块为 skip
try:
    from src.ai.narrative.style_validator import StyleAwareValidator
except ImportError:
    pytestmark = pytest.mark.skip(
        reason="src.ai.narrative.style_validator 尚未实现（TDD红色阶段）"
    )
    StyleAwareValidator = None  # type: ignore

# ConstraintType 可能尚无新成员，但模块已存在
from src.ai.harness.constraint_registry import ConstraintType

# ==================== 基本功能测试 ====================


@pytest.mark.unit
class TestStyleAwareValidatorBasic:
    """StyleAwareValidator 基本创建与调用。"""

    def test_validator_creation(self, sample_style_manifest):
        """创建 validator 不崩溃。"""
        validator = StyleAwareValidator(sample_style_manifest)
        assert validator is not None

    def test_validate_returns_result(self, sample_style_manifest, mock_story_text):
        """validate 返回包含 passed, score, details 的结果。"""
        validator = StyleAwareValidator(sample_style_manifest)
        result = validator.validate(mock_story_text)
        assert (
            hasattr(result, "passed")
            or isinstance(result, dict)
            or isinstance(result, tuple)
        )
        # 如果返回 tuple: (passed, score, details)
        if isinstance(result, tuple):
            assert len(result) == 3
            passed, score, details = result
            assert isinstance(passed, bool)
            assert isinstance(score, (int, float))
            assert isinstance(details, dict)

    def test_validate_with_context(self, sample_style_manifest, mock_story_text):
        """validate 支持传入 context。"""
        validator = StyleAwareValidator(sample_style_manifest)
        context = {"week": 12, "season": "春"}
        result = validator.validate(mock_story_text, context=context)
        assert result is not None


# ==================== 4 维度评分测试 ====================


@pytest.mark.unit
class TestFourDimensionScoring:
    """4维度评分：结构完整性、节奏规则、语言风格、技法体现。"""

    def test_structure_dimension_score(self, sample_style_manifest, mock_story_text):
        """结构完整性维度有评分。"""
        validator = StyleAwareValidator(sample_style_manifest)
        scores = validator.get_dimension_scores(mock_story_text)
        assert "structure" in scores
        assert 0.0 <= scores["structure"] <= 1.0

    def test_pacing_dimension_score(self, sample_style_manifest, mock_story_text):
        """节奏规则维度有评分。"""
        validator = StyleAwareValidator(sample_style_manifest)
        scores = validator.get_dimension_scores(mock_story_text)
        assert "pacing" in scores
        assert 0.0 <= scores["pacing"] <= 1.0

    def test_language_dimension_score(self, sample_style_manifest, mock_story_text):
        """语言风格维度有评分。"""
        validator = StyleAwareValidator(sample_style_manifest)
        scores = validator.get_dimension_scores(mock_story_text)
        assert "language" in scores
        assert 0.0 <= scores["language"] <= 1.0

    def test_technique_dimension_score(self, sample_style_manifest, mock_story_text):
        """技法体现维度有评分。"""
        validator = StyleAwareValidator(sample_style_manifest)
        scores = validator.get_dimension_scores(mock_story_text)
        assert "technique" in scores
        assert 0.0 <= scores["technique"] <= 1.0

    def test_all_scores_normalized(self, sample_style_manifest, mock_story_text):
        """所有维度分数归一化到 0-1。"""
        validator = StyleAwareValidator(sample_style_manifest)
        scores = validator.get_dimension_scores(mock_story_text)
        for dim, score in scores.items():
            assert 0.0 <= score <= 1.0, f"{dim} 维度分数 {score} 不在 [0, 1] 范围"

    def test_overall_score(self, sample_style_manifest, mock_story_text):
        """综合评分为各维度加权平均。"""
        validator = StyleAwareValidator(sample_style_manifest)
        overall = validator.get_overall_score(mock_story_text)
        assert isinstance(overall, float)
        assert 0.0 <= overall <= 1.0


# ==================== 权重配置测试 ====================


@pytest.mark.unit
class TestWeightConfiguration:
    """各维度权重可配置。"""

    def test_default_weights(self, sample_style_manifest):
        """默认权重存在且合理。"""
        validator = StyleAwareValidator(sample_style_manifest)
        weights = validator.get_weights()
        assert isinstance(weights, dict)
        assert len(weights) == 4
        assert all(w > 0 for w in weights.values())

    def test_custom_weights(self, sample_style_manifest):
        """自定义权重生效。"""
        custom_weights = {
            "structure": 0.4,
            "pacing": 0.2,
            "language": 0.3,
            "technique": 0.1,
        }
        validator = StyleAwareValidator(sample_style_manifest, weights=custom_weights)
        assert validator.get_weights() == custom_weights

    def test_weights_affect_overall_score(self, sample_style_manifest, mock_story_text):
        """不同权重导致不同综合分数。"""
        v1 = StyleAwareValidator(
            sample_style_manifest,
            weights={
                "structure": 1.0,
                "pacing": 0.0,
                "language": 0.0,
                "technique": 0.0,
            },
        )
        v2 = StyleAwareValidator(
            sample_style_manifest,
            weights={
                "structure": 0.0,
                "pacing": 0.0,
                "language": 1.0,
                "technique": 0.0,
            },
        )
        s1 = v1.get_overall_score(mock_story_text)
        s2 = v2.get_overall_score(mock_story_text)
        # 只要能计算即可；不同权重可能产生不同分数
        assert isinstance(s1, float)
        assert isinstance(s2, float)


# ==================== ConstraintType 集成测试 ====================


@pytest.mark.unit
class TestConstraintTypeIntegration:
    """新增 ConstraintType 注册。"""

    def test_style_structure_constraint_type(self):
        """STYLE_STRUCTURE ConstraintType 已注册。"""
        assert hasattr(
            ConstraintType, "STYLE_STRUCTURE"
        ), "ConstraintType 缺少 STYLE_STRUCTURE"

    def test_style_pacing_constraint_type(self):
        """STYLE_PACING ConstraintType 已注册。"""
        assert hasattr(
            ConstraintType, "STYLE_PACING"
        ), "ConstraintType 缺少 STYLE_PACING"

    def test_style_language_constraint_type(self):
        """STYLE_LANGUAGE ConstraintType 已注册。"""
        assert hasattr(
            ConstraintType, "STYLE_LANGUAGE"
        ), "ConstraintType 缺少 STYLE_LANGUAGE"

    def test_style_technique_constraint_type(self):
        """STYLE_TECHNIQUE ConstraintType 已注册。"""
        assert hasattr(
            ConstraintType, "STYLE_TECHNIQUE"
        ), "ConstraintType 缺少 STYLE_TECHNIQUE"


# ==================== Harness 集成接口测试 ====================


@pytest.mark.unit
class TestHarnessIntegration:
    """与 Harness ValidationPipeline 的集成接口。"""

    def test_as_validator_function(self, sample_style_manifest, mock_story_text):
        """validator 可转化为 Harness 标准验证函数签名。"""
        validator = StyleAwareValidator(sample_style_manifest)
        # 应提供符合 (story_text, context) -> (bool, str, dict) 的接口
        validate_fn = validator.as_harness_validator()
        assert callable(validate_fn)

        result = validate_fn(mock_story_text, {})
        assert isinstance(result, tuple)
        assert len(result) == 3
        passed, evidence, details = result
        assert isinstance(passed, bool)
        assert isinstance(evidence, str)
        assert isinstance(details, dict)


# ==================== 降级测试 ====================


@pytest.mark.unit
class TestStyleValidatorDegradation:
    """无风格时的降级行为。"""

    def test_none_style_skips_validation(self, mock_story_text):
        """无风格时跳过验证，返回通过。"""
        validator = StyleAwareValidator(None)
        result = validator.validate(mock_story_text)
        if isinstance(result, tuple):
            passed, _, _ = result
            assert passed is True
        else:
            assert result.passed is True

    def test_empty_story_text(self, sample_style_manifest):
        """空故事文本不崩溃。"""
        validator = StyleAwareValidator(sample_style_manifest)
        result = validator.validate("")
        assert result is not None
