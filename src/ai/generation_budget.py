"""Compatibility imports for the unified narrative-budget module.

New code should import from :mod:`src.ai.budgets`.  This module remains for one
stable release so existing extensions and old call sites keep working.
"""

from src.ai.budgets import (
    DisplayBudget,
    GenerationBudget,
    GenerationBudgetError,
    GenerationBudgetExceeded,
    GenerationCallTracker,
    GenerationDeadlineExceeded,
    GenerationOperation,
    InformationBudget,
    LocalizedLengthBand,
    NarrativeBudget,
    NarrativeKind,
    RecursiveRecoveryError,
    format_length_requirement,
    get_generation_budget,
    measure_narrative_length,
    measure_option_length,
    resolve_display_budget,
    resolve_narrative_budget,
    resolve_prompt_length_requirement,
)

_DAILY_BUDGETS = {
    # ★ soft limit: max_tokens 是"推荐预算"，soft_max_tokens 由 GenerationBudget
    # 自动按 2x 计算（见 budgets.GenerationBudget.__post_init__）。truncation_recovery
    # 续写时会用 soft_max_tokens 升级 max_tokens，避免续写也被同样截断。
    "fast": GenerationBudget(
        level="fast",
        min_length=350,
        max_length=500,
        max_tokens=4096,  # ★ 2048 装不下 500 字符故事, 提至 4096
        allow_quick_regeneration=False,
        allow_ai_consistency=False,
        expected_min_seconds=20,
        expected_seconds=45,
    ),
    "expert": GenerationBudget(
        level="expert",
        min_length=500,
        max_length=800,
        max_tokens=4096,
        allow_quick_regeneration=True,
        allow_ai_consistency=True,
        expected_min_seconds=45,
        expected_seconds=90,
    ),
    "master": GenerationBudget(
        level="master",
        min_length=800,
        max_length=1200,
        max_tokens=6144,
        allow_quick_regeneration=True,
        allow_ai_consistency=True,
        expected_min_seconds=75,
        expected_seconds=150,
    ),
}


def get_daily_generation_budget(level: str) -> GenerationBudget:
    """Return the v2 one-story-day budget, defaulting to expert."""
    return _DAILY_BUDGETS.get(str(level).lower(), _DAILY_BUDGETS["expert"])


__all__ = [
    "DisplayBudget", "GenerationBudget", "GenerationBudgetError",
    "GenerationBudgetExceeded", "GenerationCallTracker",
    "GenerationDeadlineExceeded", "GenerationOperation", "InformationBudget",
    "LocalizedLengthBand", "NarrativeBudget", "NarrativeKind",
    "RecursiveRecoveryError", "format_length_requirement",
    "get_daily_generation_budget", "get_generation_budget",
    "measure_narrative_length", "measure_option_length",
    "resolve_display_budget", "resolve_narrative_budget",
    "resolve_prompt_length_requirement",
]
