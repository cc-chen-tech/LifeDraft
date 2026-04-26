"""智能重试决策器。

基于验证结果和诊断报告，决定是否需要重试生成，
并构建针对性的修正指令注入到下次生成的 prompt 中。
"""

import logging
from typing import List, Optional, Tuple

from .constraint_registry import Priority
from .diagnostics import DiagnosticReport
from .quality_level import PROFILES, HarnessProfile, QualityLevel
from .validation_pipeline import ValidationResult

logger = logging.getLogger(__name__)

# 修正指令最大长度（约 500 tokens）
_MAX_CORRECTION_LENGTH = 800
# 修正指令中最多列出的问题数
_MAX_ISSUES_IN_PROMPT = 5


class RetryController:
    """智能重试控制器。

    根据验证结果和诊断报告中的违反情况，
    决定是否需要重试，并生成针对性的修正指令。

    Attributes:
        max_retries: 最大重试次数
        score_threshold: 低于此分数时建议重试
    """

    def __init__(
        self,
        max_retries: int = 2,
        score_threshold: float = 70.0,
        profile: Optional["HarnessProfile"] = None,
    ):
        """初始化重试控制器。

        Args:
            max_retries: 最大重试次数，默认 2
            score_threshold: 分数阈值，低于此值时在首次尝试后建议重试，默认 70.0
            profile: Harness 质量级别配置，传入后优先使用 profile 中的参数
        """
        self.profile = profile or PROFILES[QualityLevel.EXPERT]
        self.max_retries = self.profile.max_retries
        self.score_threshold = self.profile.score_threshold

    def should_retry(
        self,
        validation_result: ValidationResult,
        diagnostic_report: DiagnosticReport,
        attempt: int,
    ) -> Tuple[bool, Optional[str]]:
        """判断是否应该重试生成。

        根据当前尝试次数、CRITICAL 失败和分数来决策。

        Args:
            validation_result: 验证管道返回的验证结果
            diagnostic_report: 诊断器生成的诊断报告
            attempt: 当前尝试次数（从 0 开始）

        Returns:
            (是否重试, 修正指令文本)。不重试时修正指令为 None。
        """
        try:
            return self._should_retry_inner(
                validation_result, diagnostic_report, attempt
            )
        except Exception as e:
            logger.error(f"重试决策异常: {e}")
            return False, None

    def _should_retry_inner(
        self,
        validation_result: ValidationResult,
        diagnostic_report: DiagnosticReport,
        attempt: int,
    ) -> Tuple[bool, Optional[str]]:
        """内部重试决策逻辑。

        Args:
            validation_result: 验证结果
            diagnostic_report: 诊断报告
            attempt: 当前尝试次数

        Returns:
            (是否重试, 修正指令文本)
        """
        # 1. 超过最大重试次数，不再重试
        if attempt >= self.profile.max_retries:
            logger.info(
                f"已达最大重试次数 ({self.profile.max_retries})，不再重试。"
                f"最终评分: {validation_result.score:.1f}"
            )
            return False, None

        # 2. 有 CRITICAL 失败，必须重试
        if diagnostic_report.critical_count > 0:
            correction = self._build_correction_prompt(diagnostic_report)
            logger.info(
                f"检测到 {diagnostic_report.critical_count} 个 CRITICAL 违反，"
                f"触发重试 (attempt={attempt})"
            )
            return True, correction

        # 3. 大师级：HIGH 警告也触发重试
        if (
            self.profile.retry_on_high_warnings
            and len(validation_result.high_warnings) > 0
        ):
            hint = self._build_gentle_hint(validation_result)
            logger.info(
                f"MASTER 模式检测到 {len(validation_result.high_warnings)} 个 HIGH 警告，"
                f"触发重试 (attempt={attempt})"
            )
            return True, hint

        # 4. 无 CRITICAL 但分数低于阈值触发重试
        if validation_result.score < self.profile.score_threshold:
            hint = self._build_gentle_hint(validation_result)
            logger.info(
                f"评分 {validation_result.score:.1f} 低于阈值 {self.profile.score_threshold}，"
                f"触发温和重试 (attempt={attempt})"
            )
            return True, hint

        # 5. 其他情况不重试
        logger.debug(
            f"无需重试: score={validation_result.score:.1f}, "
            f"critical={diagnostic_report.critical_count}, attempt={attempt}"
        )
        return False, None

    def _build_correction_prompt(self, diagnostic_report: DiagnosticReport) -> str:
        """根据诊断报告生成针对性的修正指令。

        CRITICAL 级别的问题排在前面，最多列出 5 个问题，
        输出长度不超过 800 字符。

        Args:
            diagnostic_report: 诊断报告

        Returns:
            修正指令文本
        """
        try:
            return self._build_correction_prompt_inner(diagnostic_report)
        except Exception as e:
            logger.error(f"构建修正指令失败: {e}")
            return "【重要修正要求】请严格遵守所有约束要求重新生成故事。"

    def _build_correction_prompt_inner(
        self, diagnostic_report: DiagnosticReport
    ) -> str:
        """内部修正指令构建逻辑。

        Args:
            diagnostic_report: 诊断报告

        Returns:
            修正指令文本
        """
        # 按优先级排序：CRITICAL 在前
        priority_order = {
            Priority.CRITICAL.name: 0,
            Priority.HIGH.name: 1,
            Priority.MEDIUM.name: 2,
            Priority.LOW.name: 3,
        }
        sorted_violations = sorted(
            diagnostic_report.violations,
            key=lambda v: priority_order.get(v.get("priority", ""), 99),
        )

        # 最多取 5 个
        top_violations = sorted_violations[:_MAX_ISSUES_IN_PROMPT]

        lines: List[str] = ["【重要修正要求 - 上次生成违反了以下约束】\n"]

        for i, violation in enumerate(top_violations, 1):
            c_type = violation.get("constraint_type", "未知")
            description = violation.get("description", "约束验证失败")
            evidence = violation.get("evidence", "")
            fix = self._get_fix_for_type(c_type, diagnostic_report)

            entry = f"{i}. [{c_type}]: {description}"
            if evidence and evidence != "无法定位具体证据":
                # 证据截断到 100 字符
                ev_text = evidence[:100] + "..." if len(evidence) > 100 else evidence
                entry += f"\n   证据: {ev_text}"
            if fix:
                entry += f"\n   修正: {fix}"

            lines.append(entry)

        lines.append("\n请严格遵守以上约束重新生成故事。")

        result = "\n\n".join(lines)

        # 限制总长度不超过 800 字符
        if len(result) > _MAX_CORRECTION_LENGTH:
            result = result[: _MAX_CORRECTION_LENGTH - 3] + "..."

        return result

    def _get_fix_for_type(
        self, constraint_type: str, diagnostic_report: DiagnosticReport
    ) -> str:
        """从诊断报告的 suggested_fixes 中提取对应约束类型的修复建议。

        Args:
            constraint_type: 约束类型字符串
            diagnostic_report: 诊断报告

        Returns:
            修复建议文本，无则返回空字符串
        """
        prefix = f"[{constraint_type}] "
        for fix in diagnostic_report.suggested_fixes:
            if fix.startswith(prefix):
                return fix[len(prefix) :]
        return ""

    def _build_gentle_hint(self, validation_result: ValidationResult) -> str:
        """构建温和的修正提示。

        当没有 CRITICAL 失败但分数较低时使用，
        列出得分最低的前 3 项。

        Args:
            validation_result: 验证结果

        Returns:
            温和提示文本
        """
        try:
            return self._build_gentle_hint_inner(validation_result)
        except Exception as e:
            logger.error(f"构建温和提示失败: {e}")
            return "请更严格地遵守所有约束。"

    def _build_gentle_hint_inner(self, validation_result: ValidationResult) -> str:
        """内部温和提示构建逻辑。

        Args:
            validation_result: 验证结果

        Returns:
            温和提示文本
        """
        # 收集所有失败项
        all_failures = []
        all_failures.extend(validation_result.high_warnings)
        all_failures.extend(validation_result.medium_notes)
        all_failures.extend(validation_result.low_notes)

        failed_types = [c.constraint_type for c in all_failures if not c.passed]

        # 取前 3 个
        top3 = failed_types[:3]

        if top3:
            items = "、".join(top3)
            return f"请更严格地遵守所有约束，尤其注意: {items}"
        else:
            return "请更严格地遵守所有约束，提高故事质量。"
