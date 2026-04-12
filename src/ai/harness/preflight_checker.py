"""
Prompt 预检查器。
在 Prompt 发送给 AI 之前，检查约束是否完整注入，
提前发现静默丢失的约束。
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .constraint_registry import ConstraintRegistry, ConstraintType, Priority

logger = logging.getLogger(__name__)


@dataclass
class PreflightResult:
    """预检查结果"""

    all_present: bool  # 是否所有期望约束都存在
    missing_constraints: List[str] = field(default_factory=list)  # 缺失的约束标记
    warnings: List[str] = field(default_factory=list)  # 警告信息
    prompt_token_estimate: int = 0  # 估计的 prompt token 数
    context_completeness: Dict[str, bool] = field(default_factory=dict)  # 上下文数据完整性


class PreflightChecker:
    """Prompt 发送前的完整性检查器"""

    # 约束在 prompt 中的标记映射（用于检测约束是否被注入）
    PROMPT_MARKERS = {
        "available_people": ["可用人物", "Available Characters", "[MUST]"],
        "established_facts": ["世界事实", "Established Facts", "[MUST]"],
        "world_model": ["世界模型约束", "World Model Constraints", "[MUST]"],
        "overdue_storylines": ["剧情线", "storyline", "Storyline"],
        "character_habits": ["习惯", "habit", "[SHOULD]"],
        "foreshadowing": ["伏笔", "foreshadowing", "[SHOULD]"],
    }

    # 关键上下文数据字段
    CRITICAL_CONTEXT_FIELDS = [
        "available_people",
        "established_facts",
    ]

    OPTIONAL_CONTEXT_FIELDS = [
        "pending_storylines",
        "overdue_storylines",
        "character_habits",
        "world_model_state",
        "last_location",
    ]

    def __init__(self, registry: ConstraintRegistry):
        self.registry = registry

    def check_prompt_completeness(self, final_prompt: str, context: dict) -> PreflightResult:
        """
        检查 prompt 中是否包含了所有期望的约束标识符，
        以及上下文数据是否完整。

        Args:
            final_prompt: 最终组装的 prompt 文本
            context: 验证上下文数据

        Returns:
            PreflightResult 检查结果
        """
        missing = []
        warnings = []

        # 1. 检查 prompt 中的约束标记
        for constraint_name, markers in self.PROMPT_MARKERS.items():
            found = any(marker in final_prompt for marker in markers)
            if not found:
                missing.append(constraint_name)

        # 2. 检查 prompt token 长度（粗略估计：中文约1.5 tokens/字）
        prompt_len = len(final_prompt)
        token_estimate = int(prompt_len * 0.75)  # 中英混合的粗略估计

        if token_estimate > 8000:
            warnings.append(f"Prompt 过长: 估计 {token_estimate} tokens (建议 < 8000)")
        elif token_estimate < 1000:
            warnings.append(f"Prompt 过短: 估计 {token_estimate} tokens (可能缺少约束)")

        # 3. 检查上下文数据完整性
        context_completeness = {}
        for field_name in self.CRITICAL_CONTEXT_FIELDS:
            data = context.get(field_name)
            is_present = data is not None and (not isinstance(data, (list, str)) or len(data) > 0)
            context_completeness[field_name] = is_present
            if not is_present:
                warnings.append(f"关键上下文数据缺失: {field_name}")

        for field_name in self.OPTIONAL_CONTEXT_FIELDS:
            data = context.get(field_name)
            is_present = data is not None and (not isinstance(data, (list, str)) or len(data) > 0)
            context_completeness[field_name] = is_present

        # 4. 检查 [MUST] 标记是否存在（至少应该有一个）
        if "[MUST]" not in final_prompt:
            warnings.append("Prompt 中未检测到 [MUST] 约束标记")

        all_present = len(missing) == 0

        # 记录日志
        if not all_present:
            logger.warning(f"Preflight FAILED: missing constraints = {missing}")
        if warnings:
            logger.warning(f"Preflight warnings: {warnings}")
        else:
            logger.debug("Preflight check passed")

        return PreflightResult(
            all_present=all_present,
            missing_constraints=missing,
            warnings=warnings,
            prompt_token_estimate=token_estimate,
            context_completeness=context_completeness,
        )
