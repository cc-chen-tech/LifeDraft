"""Compatibility imports for the unified narrative-budget module.

New code should import from :mod:`src.ai.budgets`.  This module remains for one
stable release so existing extensions and old call sites keep working.
"""

from src.ai.budgets import (DisplayBudget, GenerationBudget,
                            GenerationBudgetError, GenerationBudgetExceeded,
                            GenerationCallTracker, GenerationDeadlineExceeded,
                            GenerationOperation, InformationBudget,
                            LocalizedLengthBand, NarrativeBudget,
                            NarrativeKind, RecursiveRecoveryError,
                            format_length_requirement, get_generation_budget,
                            measure_narrative_length, resolve_narrative_budget,
                            resolve_prompt_length_requirement)

__all__ = [
    "DisplayBudget",
    "GenerationBudget",
    "GenerationBudgetError",
    "GenerationBudgetExceeded",
    "GenerationCallTracker",
    "GenerationDeadlineExceeded",
    "GenerationOperation",
    "InformationBudget",
    "LocalizedLengthBand",
    "NarrativeBudget",
    "NarrativeKind",
    "RecursiveRecoveryError",
    "format_length_requirement",
    "get_generation_budget",
    "measure_narrative_length",
    "resolve_narrative_budget",
    "resolve_prompt_length_requirement",
]
