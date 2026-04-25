"""Harness 质量级别模块导入验证测试 (Layer 2)."""

import pytest


def test_quality_level_module_importable():
    """quality_level 模块可导入且包含预期符号."""
    from src.ai.harness.quality_level import QualityLevel, HarnessProfile, PROFILES

    assert QualityLevel.FAST.value == "fast"
    assert QualityLevel.EXPERT.value == "expert"
    assert QualityLevel.MASTER.value == "master"
    assert len(PROFILES) == 3
    assert all(isinstance(p, HarnessProfile) for p in PROFILES.values())


def test_polish_controller_importable():
    """polish_controller 模块可导入且 PolishController 存在."""
    from src.ai.harness.polish_controller import PolishController

    assert PolishController is not None


def test_retry_controller_accepts_profile():
    """RetryController 支持通过 profile 参数构造."""
    from src.ai.harness.retry_controller import RetryController
    from src.ai.harness.quality_level import PROFILES, QualityLevel

    profile = PROFILES[QualityLevel.EXPERT]
    controller = RetryController(profile=profile)
    assert controller.profile == profile


def test_validation_pipeline_accepts_profile():
    """ValidationPipeline.validate 支持 profile 参数."""
    from src.ai.harness.validation_pipeline import ValidationPipeline
    from src.ai.harness.constraint_registry import ConstraintRegistry
    from src.ai.harness.quality_level import PROFILES, QualityLevel

    registry = ConstraintRegistry()
    pipeline = ValidationPipeline(registry)
    profile = PROFILES[QualityLevel.FAST]

    # 验证方法签名支持 profile 参数（空文本和空上下文，不会触发实际验证器）
    result = pipeline.validate("", {}, profile=profile)
    assert result is not None
    assert hasattr(result, "passed")


def test_era_validator_importable():
    """era_validator 模块可导入且 validate_era_consistency 存在."""
    from src.ai.harness.era_validator import validate_era_consistency, _ANCIENT_FORBIDDEN_MODERN

    assert validate_era_consistency is not None
    assert isinstance(_ANCIENT_FORBIDDEN_MODERN, list)
    assert len(_ANCIENT_FORBIDDEN_MODERN) > 0


def test_era_validator_runs_with_context():
    """validate_era_consistency 接受 story_text 和 context 并返回三元组."""
    from src.ai.harness.era_validator import validate_era_consistency

    passed, evidence, info = validate_era_consistency(
        "test", {"era": "宋朝", "era_type": "ancient"}
    )
    assert isinstance(passed, bool)
    assert isinstance(evidence, str)
    assert isinstance(info, dict)
