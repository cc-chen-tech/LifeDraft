"""约束违反诊断与证据定位模块。

对验证失败的约束进行证据提取和诊断报告生成，
帮助重试控制器做出精准的修正决策。
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List

from .constraint_registry import Priority
from .validation_pipeline import ConstraintCheckResult, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticReport:
    """诊断报告，包含所有违反约束的证据和修复建议。

    Attributes:
        violations: 违反详情列表，每项包含 constraint_type, priority, evidence, description
        evidence_map: 约束类型到证据文本的映射
        summary: 人类可读的诊断摘要
        suggested_fixes: 修复建议列表
        total_violations: 违反总数
        critical_count: CRITICAL 级别违反数量
    """

    violations: List[dict] = field(default_factory=list)
    evidence_map: Dict[str, str] = field(default_factory=dict)
    summary: str = ""
    suggested_fixes: List[str] = field(default_factory=list)
    total_violations: int = 0
    critical_count: int = 0


# 约束类型到中文描述的映射（用于生成修复建议）
_CONSTRAINT_FIX_HINTS: Dict[str, str] = {
    "available_people": "仅使用可用人物列表中的角色，移除未知人名",
    "no_meta_narration": "删除所有打破第四面墙或跳脱叙事的表达",
    "third_person": "将所有第一人称（我、我们）改为第三人称叙事",
    "decision_point_ending": "确保故事结尾停在一个具体的决策点，给出选择",
    "overdue_storylines": "在本轮故事中推进或提及过期的剧情线",
    "scene_continuity": "确保故事开头与上一轮结尾的场景地点连贯衔接",
    "established_facts": "检查并修正与已建立事实矛盾的内容",
    "no_fabrication": "移除编造的过往事件，所有回忆必须有据可查",
    "high_storylines": "至少涉及一条高重要性剧情线",
    "character_consistency": "确保角色行为与已建立的性格画像一致",
    "character_habits": "在故事中自然体现人物习惯",
    "foreshadowing": "在故事中回应已激活的伏笔种子",
    "medium_storylines": "考虑延续中重要性剧情线",
    "logic_constraints": "检查时间、季节、天气等逻辑一致性",
    "anti_repetition": "避免重复的段落或句式",
}

# 第一人称关键词模式
_FIRST_PERSON_PATTERN = re.compile(r"[我我们咱咱们]")


class ConstraintViolationDiagnostic:
    """约束违反诊断器。

    从故事文本中提取违反约束的具体证据，
    生成包含证据定位和修复建议的诊断报告。
    纯规则与文本匹配，不调用任何 AI/LLM。
    """

    def locate_evidence(
        self, story_text: str, violation_type: str, details: dict
    ) -> str:
        """根据违反类型从故事文本中提取证据段落。

        Args:
            story_text: 故事全文
            violation_type: 约束类型字符串（如 'available_people'）
            details: 验证器返回的详细信息字典

        Returns:
            包含证据的文本片段，不超过 300 字
        """
        try:
            evidence = self._locate_evidence_inner(story_text, violation_type, details)
            # 截断到 300 字
            if len(evidence) > 300:
                evidence = evidence[:297] + "..."
            return evidence
        except Exception as e:
            logger.error(f"证据定位失败 [{violation_type}]: {e}")
            return "无法定位具体证据"

    def _locate_evidence_inner(
        self, story_text: str, violation_type: str, details: dict
    ) -> str:
        """内部证据定位逻辑。

        Args:
            story_text: 故事全文
            violation_type: 约束类型
            details: 详细信息

        Returns:
            证据文本
        """
        if violation_type == "available_people":
            return self._locate_unknown_people(story_text, details)
        elif violation_type == "no_meta_narration":
            return self._locate_meta_narration(details)
        elif violation_type == "third_person":
            return self._locate_first_person(story_text)
        elif violation_type == "decision_point_ending":
            return story_text[-200:] if len(story_text) > 200 else story_text
        elif violation_type == "overdue_storylines":
            not_mentioned = details.get("not_mentioned", [])
            if not_mentioned:
                return "未推进的过期剧情线: " + "、".join(str(s) for s in not_mentioned)
            return "存在未推进的过期剧情线"
        elif violation_type == "scene_continuity":
            return story_text[:200] if len(story_text) > 200 else story_text
        else:
            return "无法定位具体证据"

    def _locate_unknown_people(self, story_text: str, details: dict) -> str:
        """找出包含未知人名的句子。

        Args:
            story_text: 故事全文
            details: 应包含 'unknown_names' 键

        Returns:
            包含未知人名的句子
        """
        unknown_names = details.get("unknown_names", [])
        if not unknown_names:
            return "检测到未知人物，但无法提取具体名字"

        sentences = re.split(r"[。！？\n]", story_text)
        matched_sentences = []
        for name in unknown_names:
            for sentence in sentences:
                if name in sentence and sentence.strip():
                    matched_sentences.append(
                        f"「{sentence.strip()}」(未知人物: {name})"
                    )
                    break

        if matched_sentences:
            return "; ".join(matched_sentences)
        return f"故事中出现了未知人物: {'、'.join(unknown_names)}"

    def _locate_meta_narration(self, details: dict) -> str:
        """从 details 中提取跳脱叙事的上下文。

        Args:
            details: 应包含 'violations' 键

        Returns:
            违反的上下文文本
        """
        violations = details.get("violations", [])
        if violations:
            return "; ".join(str(v) for v in violations[:5])
        return "检测到跳脱叙事内容"

    def _locate_first_person(self, story_text: str) -> str:
        """找出包含第一人称的句子。

        Args:
            story_text: 故事全文

        Returns:
            包含第一人称的句子
        """
        sentences = re.split(r"[。！？\n]", story_text)
        matched = []
        for sentence in sentences:
            if _FIRST_PERSON_PATTERN.search(sentence) and sentence.strip():
                matched.append(f"「{sentence.strip()}」")
                if len(matched) >= 3:
                    break

        if matched:
            return "包含第一人称的句子: " + "; ".join(matched)
        return "检测到第一人称用法"

    def generate_report(
        self, story_text: str, validation_result: ValidationResult
    ) -> DiagnosticReport:
        """生成完整的诊断报告。

        遍历验证结果中所有失败的约束检查，提取证据并生成修复建议。

        Args:
            story_text: 故事全文
            validation_result: 验证管道返回的验证结果

        Returns:
            DiagnosticReport 诊断报告
        """
        try:
            return self._generate_report_inner(story_text, validation_result)
        except Exception as e:
            logger.error(f"诊断报告生成失败: {e}")
            return DiagnosticReport(
                summary=f"诊断报告生成失败: {e}",
                suggested_fixes=["请检查约束配置和验证结果"],
            )

    def _generate_report_inner(
        self, story_text: str, validation_result: ValidationResult
    ) -> DiagnosticReport:
        """内部报告生成逻辑。

        Args:
            story_text: 故事全文
            validation_result: 验证结果

        Returns:
            DiagnosticReport
        """
        report = DiagnosticReport()

        # 收集所有失败项（按优先级分组）
        all_failures: List[ConstraintCheckResult] = []
        all_failures.extend(validation_result.critical_failures)
        all_failures.extend(validation_result.high_warnings)
        all_failures.extend(validation_result.medium_notes)
        all_failures.extend(validation_result.low_notes)

        # 只处理未通过的
        failed_checks = [c for c in all_failures if not c.passed]

        for check in failed_checks:
            evidence = self.locate_evidence(
                story_text, check.constraint_type, check.details
            )

            violation_entry = {
                "constraint_type": check.constraint_type,
                "priority": check.priority,
                "evidence": evidence,
                "description": check.evidence
                or f"约束 {check.constraint_type} 验证失败",
            }
            report.violations.append(violation_entry)
            report.evidence_map[check.constraint_type] = evidence

            # 生成修复建议
            fix_hint = _CONSTRAINT_FIX_HINTS.get(check.constraint_type)
            if fix_hint:
                report.suggested_fixes.append(f"[{check.constraint_type}] {fix_hint}")
            else:
                report.suggested_fixes.append(
                    f"[{check.constraint_type}] 请修正该约束的违反"
                )

            if check.priority == Priority.CRITICAL.name:
                report.critical_count += 1

        report.total_violations = len(report.violations)

        # 生成摘要
        report.summary = self._build_summary(report, validation_result)

        logger.info(
            f"诊断完成: {report.total_violations} 项违反, "
            f"其中 CRITICAL {report.critical_count} 项"
        )

        return report

    def _build_summary(
        self, report: DiagnosticReport, validation_result: ValidationResult
    ) -> str:
        """生成人类可读的诊断摘要。

        Args:
            report: 当前诊断报告
            validation_result: 验证结果

        Returns:
            摘要字符串
        """
        if report.total_violations == 0:
            return f"所有约束检查通过，评分 {validation_result.score:.1f}/100"

        parts = [
            f"发现 {report.total_violations} 项约束违反"
            f"（CRITICAL: {report.critical_count}）, "
            f"评分 {validation_result.score:.1f}/100。"
        ]

        # 列出 CRITICAL 违反
        critical_types = [
            v["constraint_type"]
            for v in report.violations
            if v["priority"] == Priority.CRITICAL.name
        ]
        if critical_types:
            parts.append(f"关键违反: {', '.join(critical_types)}")

        return " ".join(parts)
