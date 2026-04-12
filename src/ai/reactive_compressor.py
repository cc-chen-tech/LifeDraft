"""Reactive context compression for Harness retry loops.

Inspired by Claude Code's reactive compact strategy. When Harness validation
fails and retry is needed, dynamically compress context to free token budget
for correction instructions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Default trim order - matches _helpers.py._BUDGET_TRIM_ORDER
DEFAULT_BUDGET_TRIM_ORDER: List[str] = [
    "preference_hint",
    "fate_echo",
    "conflict_directive",
    "style_constraints",
    "overused_phrases",
    "vector_context",
    "arc_hint",
    "foreshadowing",
    "character_habits",
    "pending_storylines",
]

# Protected fields that should never be trimmed
PROTECTED_FIELDS: List[str] = [
    "critical_summary",
    "established_facts",
    "world_model",
]


@dataclass
class CompactionResult:
    """Result of reactive context compression."""
    original_token_count: int
    compressed_token_count: int
    removed_sections: List[str] = field(default_factory=list)
    budget_factor: float = 1.0


class ReactiveCompressor:
    """Compresses prompt context reactively during Harness retry loops."""

    def __init__(self, budget_trim_order: Optional[List[str]] = None) -> None:
        raise NotImplementedError

    def should_compact(self, prompt_tokens: int, max_tokens: int, threshold: float = 0.85) -> bool:
        """Check if compaction is needed.

        Returns True when prompt_tokens > max_tokens * threshold.
        """
        raise NotImplementedError

    def compact(
        self,
        constraint_texts: Dict[str, str],
        target_reduction: float = 0.5,
    ) -> CompactionResult:
        """Compress constraint texts by removing low-priority sections.

        Args:
            constraint_texts: Dict of section_name -> text content
            target_reduction: Target reduction ratio (0.5 = remove 50% of compressible tokens)

        Returns:
            CompactionResult with compression details
        """
        raise NotImplementedError

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough: len/2 for CJK, len/4 for English)."""
        raise NotImplementedError
