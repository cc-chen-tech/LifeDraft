"""Harness 质量级别配置系统.

定义快速(fast)、专家(expert)、大师(master)三级约束强度，
为不同使用场景提供差异化的验证、重试和精修策略.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Set

from .constraint_registry import Priority


class QualityLevel(str, Enum):
    """故事生成质量级别."""

    FAST = "fast"  # 快速：最小延迟，零校验零重试
    EXPERT = "expert"  # 专家：平衡质量与速度（默认）
    MASTER = "master"  # 大师：严格校验 + 多轮重试 + 事后精修


# 中观/宏观叙事验证器类型集合
NARRATIVE_VALIDATOR_TYPES = {
    "three_act_structure",
    "pacing_variety",
    "arc_hint_compliance",
    "world_event_integration",
    "conflict_directive_compliance",
}


@dataclass(frozen=True)
class HarnessProfile:
    """给定 QualityLevel 下的完整 Harness 行为配置."""

    level: QualityLevel

    # --- 验证范围 ---
    enabled_priorities: Set[Priority]  # 启用哪些优先级的约束
    skip_preflight: bool  # 是否跳过 preflight
    skip_ai_consistency_check: bool  # 是否跳过 ConsistencyValidator

    # --- 重试策略 ---
    max_retries: int  # 最大重试次数
    score_threshold: float  # 触发重试的分数阈值
    retry_on_high_warnings: bool  # HIGH 级别警告是否触发重试
    enforce_validation_on_all_attempts: bool  # 是否每次 attempt 都校验

    # --- 大师级精修 ---
    enable_polish: bool  # 是否启用事后精修
    polish_score_threshold: float  # 低于此分触发精修
    max_polish_rounds: int  # 最大精修轮数

    # --- Prompt 注入策略 ---
    prompt_constraint_mode: str  # "minimal" / "standard" / "strict"
    include_narrative_validators: bool  # 是否启用中观/宏观叙事验证


PROFILES = {
    QualityLevel.FAST: HarnessProfile(
        level=QualityLevel.FAST,
        enabled_priorities={Priority.CRITICAL},
        skip_preflight=True,
        skip_ai_consistency_check=True,
        max_retries=0,
        score_threshold=0.0,
        retry_on_high_warnings=False,
        enforce_validation_on_all_attempts=False,
        enable_polish=False,
        polish_score_threshold=0.0,
        max_polish_rounds=0,
        prompt_constraint_mode="minimal",
        include_narrative_validators=False,
    ),
    QualityLevel.EXPERT: HarnessProfile(
        level=QualityLevel.EXPERT,
        enabled_priorities={Priority.CRITICAL, Priority.HIGH, Priority.MEDIUM, Priority.LOW},
        skip_preflight=False,
        skip_ai_consistency_check=False,
        max_retries=2,
        score_threshold=70.0,
        retry_on_high_warnings=False,
        enforce_validation_on_all_attempts=True,
        enable_polish=False,
        polish_score_threshold=0.0,
        max_polish_rounds=0,
        prompt_constraint_mode="standard",
        include_narrative_validators=True,
    ),
    QualityLevel.MASTER: HarnessProfile(
        level=QualityLevel.MASTER,
        enabled_priorities={Priority.CRITICAL, Priority.HIGH, Priority.MEDIUM, Priority.LOW},
        skip_preflight=False,
        skip_ai_consistency_check=False,
        max_retries=4,
        score_threshold=85.0,
        retry_on_high_warnings=True,
        enforce_validation_on_all_attempts=True,
        enable_polish=True,
        polish_score_threshold=90.0,
        max_polish_rounds=2,
        prompt_constraint_mode="strict",
        include_narrative_validators=True,
    ),
}
