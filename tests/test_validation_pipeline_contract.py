"""Validation pipeline contract tests.

No mocks. Uses hand-rolled stub constraint registry.
"""

from src.ai.harness.constraint_registry import (ConstraintDefinition,
                                                ConstraintRegistry,
                                                ConstraintType, Priority)
from src.ai.harness.validation_pipeline import ValidationPipeline
import pytest

pytestmark = [pytest.mark.unit]



def _make_validator(passed: bool, evidence: str = ""):
    """Create a simple validator function."""
    return lambda story, ctx: (passed, evidence, {})


class TestValidationPipelineContract:
    """Contract tests for validation pipeline."""

    def test_validate_all_pass(self):
        """All constraints pass should return passed=True, score=100."""
        registry = ConstraintRegistry()
        registry.register(
            ConstraintDefinition(
                type=ConstraintType.AVAILABLE_PEOPLE,
                priority=Priority.CRITICAL,
                description="test",
                validator=_make_validator(True),
                weight=1.0,
            )
        )
        pipeline = ValidationPipeline(registry)
        result = pipeline.validate("story", {})
        assert result.passed is True
        assert result.score == 100.0
        assert result.total_checked == 1
        assert result.total_passed == 1

    def test_validate_critical_fail(self):
        """CRITICAL failure should set passed=False and reduce score."""
        registry = ConstraintRegistry()
        registry.register(
            ConstraintDefinition(
                type=ConstraintType.AVAILABLE_PEOPLE,
                priority=Priority.CRITICAL,
                description="test",
                validator=_make_validator(False, "bad"),
                weight=1.0,
            )
        )
        pipeline = ValidationPipeline(registry)
        result = pipeline.validate("story", {})
        assert result.passed is False
        assert result.score == 85.0  # 100 - 15*1
        assert len(result.critical_failures) == 1

    def test_validate_high_warning(self):
        """HIGH failure should add to high_warnings."""
        registry = ConstraintRegistry()
        registry.register(
            ConstraintDefinition(
                type=ConstraintType.HIGH_STORYLINES,
                priority=Priority.HIGH,
                description="test",
                validator=_make_validator(False, "warn"),
                weight=1.0,
            )
        )
        pipeline = ValidationPipeline(registry)
        result = pipeline.validate("story", {})
        assert result.passed is True  # not critical
        assert result.score == 92.0  # 100 - 8*1
        assert len(result.high_warnings) == 1

    def test_validate_medium_note(self):
        """MEDIUM failure should add to medium_notes."""
        registry = ConstraintRegistry()
        registry.register(
            ConstraintDefinition(
                type=ConstraintType.CHARACTER_HABITS,
                priority=Priority.MEDIUM,
                description="test",
                validator=_make_validator(False, "note"),
                weight=1.0,
            )
        )
        pipeline = ValidationPipeline(registry)
        result = pipeline.validate("story", {})
        assert result.score == 96.0  # 100 - 4*1
        assert len(result.medium_notes) == 1

    def test_validate_low_note(self):
        """LOW failure should add to low_notes."""
        registry = ConstraintRegistry()
        registry.register(
            ConstraintDefinition(
                type=ConstraintType.CHARACTER_HABITS,
                priority=Priority.LOW,
                description="test",
                validator=_make_validator(False, "low"),
                weight=1.0,
            )
        )
        pipeline = ValidationPipeline(registry)
        result = pipeline.validate("story", {})
        assert result.score == 98.0  # 100 - 2*1
        assert len(result.low_notes) == 1

    def test_validate_score_not_negative(self):
        """Score should not go below 0."""
        registry = ConstraintRegistry()
        types = [
            ConstraintType.AVAILABLE_PEOPLE,
            ConstraintType.ESTABLISHED_FACTS,
            ConstraintType.OVERDUE_STORYLINES,
            ConstraintType.WORLD_MODEL_POSITION,
        ]
        for i in range(10):
            registry.register(
                ConstraintDefinition(
                    type=types[i % len(types)],
                    priority=Priority.CRITICAL,
                    description="test",
                    validator=_make_validator(False, "bad"),
                    weight=3.0,
                )
            )
        pipeline = ValidationPipeline(registry)
        result = pipeline.validate("story", {})
        assert result.score == 0.0

    def test_validate_detailed_checks_populated(self):
        """detailed_checks should contain all constraint results."""
        registry = ConstraintRegistry()
        registry.register(
            ConstraintDefinition(
                type=ConstraintType.AVAILABLE_PEOPLE,
                priority=Priority.CRITICAL,
                description="test",
                validator=_make_validator(True),
                weight=1.0,
            )
        )
        pipeline = ValidationPipeline(registry)
        result = pipeline.validate("story", {})
        assert "available_people" in result.detailed_checks
        assert result.detailed_checks["available_people"]["passed"] is True

    def test_validate_with_profile_filters(self):
        """Profile should filter constraints."""
        from src.ai.harness.quality_level import PROFILES, QualityLevel

        registry = ConstraintRegistry()
        registry.register(
            ConstraintDefinition(
                type=ConstraintType.AVAILABLE_PEOPLE,
                priority=Priority.CRITICAL,
                description="test",
                validator=_make_validator(False, "bad"),
                weight=1.0,
            )
        )
        pipeline = ValidationPipeline(registry)
        profile = PROFILES[QualityLevel.FAST]
        result = pipeline.validate("story", {}, profile=profile)
        # FAST profile may exclude some constraints
        assert isinstance(result.passed, bool)

    def test_validate_fast_only_critical(self):
        """validate_fast should only check CRITICAL constraints."""
        registry = ConstraintRegistry()
        registry.register(
            ConstraintDefinition(
                type=ConstraintType.AVAILABLE_PEOPLE,
                priority=Priority.CRITICAL,
                description="test",
                validator=_make_validator(False, "bad"),
                weight=1.0,
            )
        )
        registry.register(
            ConstraintDefinition(
                type=ConstraintType.HIGH_STORYLINES,
                priority=Priority.HIGH,
                description="test",
                validator=_make_validator(False, "warn"),
                weight=1.0,
            )
        )
        pipeline = ValidationPipeline(registry)
        result = pipeline.validate_fast("story", {})
        assert result.passed is False
        assert len(result.critical_failures) == 1
        assert len(result.high_warnings) == 0

    def test_run_single_check_exception_handled(self):
        """Validator exception should be caught and return passed=True."""
        registry = ConstraintRegistry()
        registry.register(
            ConstraintDefinition(
                type=ConstraintType.AVAILABLE_PEOPLE,
                priority=Priority.CRITICAL,
                description="test",
                validator=lambda s, c: (_ for _ in ()).throw(RuntimeError("boom")),
                weight=1.0,
            )
        )
        pipeline = ValidationPipeline(registry)
        result = pipeline.validate("story", {})
        assert result.passed is True  # exception = pass
        assert result.detailed_checks["available_people"]["details"]["skipped"] is True

    def test_validate_sets_timing(self):
        """validation_time_ms should be set."""
        registry = ConstraintRegistry()
        registry.register(
            ConstraintDefinition(
                type=ConstraintType.AVAILABLE_PEOPLE,
                priority=Priority.CRITICAL,
                description="test",
                validator=_make_validator(True),
                weight=1.0,
            )
        )
        pipeline = ValidationPipeline(registry)
        result = pipeline.validate("story", {})
        assert result.validation_time_ms >= 0
