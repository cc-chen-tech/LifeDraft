"""
多层验证管道。
对 AI 生成的故事文本进行分层验证，
快速定位违反的约束。
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any

from .constraint_registry import ConstraintRegistry, Priority, ConstraintDefinition

logger = logging.getLogger(__name__)


@dataclass
class ConstraintCheckResult:
    """单个约束的检查结果"""

    constraint_type: str
    priority: str
    passed: bool
    evidence: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """完整验证结果"""

    passed: bool  # 是否通过（无 CRITICAL 失败）
    score: float = 100.0  # 约束遵守度评分 (0-100)
    critical_failures: List[ConstraintCheckResult] = field(default_factory=list)
    high_warnings: List[ConstraintCheckResult] = field(default_factory=list)
    medium_notes: List[ConstraintCheckResult] = field(default_factory=list)
    low_notes: List[ConstraintCheckResult] = field(default_factory=list)
    detailed_checks: Dict[str, Dict] = field(default_factory=dict)
    validation_time_ms: float = 0.0
    total_checked: int = 0
    total_passed: int = 0


class ValidationPipeline:
    """多层验证管道"""

    # 各优先级的扣分权重
    PENALTY_WEIGHTS = {
        Priority.CRITICAL: 15.0,
        Priority.HIGH: 8.0,
        Priority.MEDIUM: 4.0,
        Priority.LOW: 2.0,
    }

    def __init__(self, registry: ConstraintRegistry):
        self.registry = registry

    def validate(self, story_text: str, context: dict) -> ValidationResult:
        """
        对故事文本执行完整验证（所有约束）。

        Args:
            story_text: AI 生成的故事文本
            context: 验证上下文，包含 available_people, established_facts,
                     pending_storylines, overdue_storylines, world_model_state,
                     character_habits, last_location 等

        Returns:
            ValidationResult 验证结果
        """
        start_time = time.time()

        constraints = self.registry.get_all_for_validation()

        result = ValidationResult(passed=True)
        score = 100.0

        for defn in constraints:
            check = self._run_single_check(defn, story_text, context)

            # 归类结果
            if not check.passed:
                penalty = self.PENALTY_WEIGHTS.get(defn.priority, 4.0) * defn.weight
                score -= penalty

                if defn.priority == Priority.CRITICAL:
                    result.critical_failures.append(check)
                    result.passed = False
                elif defn.priority == Priority.HIGH:
                    result.high_warnings.append(check)
                elif defn.priority == Priority.MEDIUM:
                    result.medium_notes.append(check)
                else:
                    result.low_notes.append(check)

            # 记录详细结果
            result.detailed_checks[check.constraint_type] = {
                "passed": check.passed,
                "priority": check.priority,
                "evidence": check.evidence,
                "details": check.details,
            }

            result.total_checked += 1
            if check.passed:
                result.total_passed += 1

        result.score = max(0.0, score)
        result.validation_time_ms = (time.time() - start_time) * 1000

        # 日志
        if not result.passed:
            logger.warning(
                f"Validation FAILED: score={result.score:.1f}, "
                f"critical={len(result.critical_failures)}, "
                f"warnings={len(result.high_warnings)}, "
                f"time={result.validation_time_ms:.0f}ms"
            )
        else:
            logger.info(
                f"Validation passed: score={result.score:.1f}, "
                f"checked={result.total_checked}, "
                f"time={result.validation_time_ms:.0f}ms"
            )

        return result

    def validate_fast(self, story_text: str, context: dict) -> ValidationResult:
        """
        快速验证 — 仅检查 CRITICAL 级别的约束。
        用于需要快速反馈的场景（如流式生成的中间检查）。

        Args:
            story_text: AI 生成的故事文本
            context: 验证上下文

        Returns:
            ValidationResult（仅包含 CRITICAL 级别结果）
        """
        start_time = time.time()

        critical_constraints = self.registry.get_critical_constraints()

        result = ValidationResult(passed=True)
        score = 100.0

        for defn in critical_constraints:
            check = self._run_single_check(defn, story_text, context)

            if not check.passed:
                penalty = self.PENALTY_WEIGHTS[Priority.CRITICAL] * defn.weight
                score -= penalty
                result.critical_failures.append(check)
                result.passed = False

            result.detailed_checks[check.constraint_type] = {
                "passed": check.passed,
                "priority": check.priority,
                "evidence": check.evidence,
                "details": check.details,
            }

            result.total_checked += 1
            if check.passed:
                result.total_passed += 1

        result.score = max(0.0, score)
        result.validation_time_ms = (time.time() - start_time) * 1000

        logger.debug(
            f"Fast validation: passed={result.passed}, "
            f"score={result.score:.1f}, "
            f"time={result.validation_time_ms:.0f}ms"
        )

        return result

    def _run_single_check(
        self, defn: ConstraintDefinition, story_text: str, context: dict
    ) -> ConstraintCheckResult:
        """
        执行单个约束检查，包含异常保护。

        Args:
            defn: 约束定义
            story_text: 故事文本
            context: 验证上下文

        Returns:
            ConstraintCheckResult
        """
        try:
            passed, evidence, details = defn.validator(story_text, context)
            return ConstraintCheckResult(
                constraint_type=defn.type.value,
                priority=defn.priority.name,
                passed=passed,
                evidence=evidence,
                details=details,
            )
        except Exception as e:
            logger.error(f"Validator error for {defn.type.value}: {e}")
            # 验证器异常时默认通过（不阻塞生成流程）
            return ConstraintCheckResult(
                constraint_type=defn.type.value,
                priority=defn.priority.name,
                passed=True,
                evidence="",
                details={"error": str(e), "skipped": True},
            )
