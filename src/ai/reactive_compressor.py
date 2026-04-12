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
    "foreshadowing_technique_hint",
    "fate_echo_hint",
    "arc_hint",
    "conflict_directive",
    "world_event_context",
    "style_constraints",
    "overused_phrases",
    "vector_context",
    "habits",
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
        self._trim_order = budget_trim_order or list(DEFAULT_BUDGET_TRIM_ORDER)

    def should_compact(self, prompt_tokens: int, max_tokens: int, threshold: float = 0.85) -> bool:
        """Check if compaction is needed.

        Returns True when prompt_tokens > max_tokens * threshold.
        """
        return prompt_tokens > max_tokens * threshold

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
        original_total = sum(self.estimate_tokens(text) for text in constraint_texts.values())
        target_remove = int(original_total * target_reduction)
        removed_tokens = 0
        removed_sections: List[str] = []

        result_texts = dict(constraint_texts)

        for field_name in self._trim_order:
            if removed_tokens >= target_remove:
                break
            if field_name not in result_texts:
                continue
            if field_name in PROTECTED_FIELDS:
                continue

            field_tokens = self.estimate_tokens(result_texts[field_name])

            if field_tokens <= 0:
                continue

            remaining_to_remove = target_remove - removed_tokens

            if remaining_to_remove >= field_tokens:
                del result_texts[field_name]
                removed_tokens += field_tokens
                removed_sections.append(field_name)
            else:
                keep_ratio = 1.0 - (remaining_to_remove / field_tokens)
                keep_chars = max(10, int(len(result_texts[field_name]) * keep_ratio))
                result_texts[field_name] = result_texts[field_name][:keep_chars] + "..."
                removed_tokens += remaining_to_remove
                removed_sections.append(f"{field_name}(truncated)")

        compressed_total = sum(self.estimate_tokens(text) for text in result_texts.values())

        return CompactionResult(
            original_token_count=original_total,
            compressed_token_count=compressed_total,
            removed_sections=removed_sections,
            budget_factor=compressed_total / max(original_total, 1),
        )

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough: len/2 for CJK, len/4 for English)."""
        if not text:
            return 0
        cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff" or "\u3000" <= c <= "\u303f")
        other_count = len(text) - cjk_count
        return cjk_count + max(1, other_count // 4)
