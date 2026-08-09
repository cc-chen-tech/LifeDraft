"""Localized narrative budgets and request-scoped provider call accounting.

Product length, model output tokens, provider calls, and wall-clock deadlines
are deliberately separate.  Callers resolve a budget once at request entry and
share one :class:`GenerationCallTracker` with nested repair/recovery services.
"""

from __future__ import annotations

import math
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable, Iterator, Literal, Optional

ABSOLUTE_MAX_NARRATIVE_CHARS = 32_000


class NarrativeKind(str, Enum):
    OPENING = "opening"
    ROUND = "round"
    CONTINUATION = "continuation"


class GenerationOperation(str, Enum):
    GENERATE = "generate"
    REWRITE = "rewrite"
    REGENERATE = "regenerate"
    COMPRESS = "compress"


LengthUnit = Literal["characters", "words"]
CallCategory = Literal["prose", "validation", "option"]


@dataclass(frozen=True)
class LocalizedLengthBand:
    target_min: int
    target_max: int
    compression_threshold: int
    absolute_max_chars: int
    unit: LengthUnit


@dataclass(frozen=True)
class NarrativeBudget:
    kind: NarrativeKind
    operation: GenerationOperation
    quality_level: str
    language: str
    length: LocalizedLengthBand
    max_output_tokens: int
    prose_call_limit: int
    validation_call_limit: int
    option_call_limit: int
    total_deadline_seconds: int

    @property
    def total_call_limit(self) -> int:
        return (
            self.prose_call_limit + self.validation_call_limit + self.option_call_limit
        )

    def exceeds_absolute_limit(self, text: str) -> bool:
        return len(text) > self.length.absolute_max_chars


@dataclass(frozen=True)
class DisplayBudget:
    option_count: int
    target_min: int
    target_max: int
    repair_threshold: int
    option_call_limit: int
    max_display_lines: int
    unit: LengthUnit


@dataclass(frozen=True)
class InformationBudget:
    summary_kind: str
    required_coverage: tuple[str, ...]
    compression_threshold: int
    unit: LengthUnit


@dataclass(frozen=True)
class GenerationBudget:
    """One-release adapter for callers of the former round-only budget API."""

    level: str
    min_length: int
    max_length: int
    max_tokens: int
    allow_quick_regeneration: bool
    allow_ai_consistency: bool
    expected_min_seconds: int
    expected_seconds: int

    def length_requirement(self, language: str) -> str:
        if _normalized_language(language) == "zh":
            return f"故事应该{self.min_length}-{self.max_length}字"
        return f"Story should be {self.min_length}-{self.max_length} words"

    def progress_expectation(self, language: str) -> str:
        if _normalized_language(language) == "zh":
            return f"通常 {self.expected_min_seconds}-{self.expected_seconds} 秒"
        return f"Usually {self.expected_min_seconds}-{self.expected_seconds} seconds"


class GenerationBudgetError(RuntimeError):
    """Base class for request budget exhaustion."""


class GenerationBudgetExceeded(GenerationBudgetError):
    """A provider call would exceed its category allowance."""


class GenerationDeadlineExceeded(GenerationBudgetError):
    """A provider call would start after the request deadline."""


class RecursiveRecoveryError(GenerationBudgetError):
    """A recovery call attempted to start a nested recovery sequence."""


_ZH_ROUND_BANDS = {
    "fast": (400, 700, 1400),
    "expert": (800, 1400, 2400),
    "master": (1200, 2200, 4000),
}
_EN_ROUND_BANDS = {
    "fast": (250, 450, 900),
    "expert": (500, 900, 1500),
    "master": (800, 1400, 2500),
}
_ZH_KIND_BANDS = {
    NarrativeKind.OPENING: (300, 500, 1000),
    NarrativeKind.CONTINUATION: (400, 700, 1400),
}
_EN_KIND_BANDS = {
    NarrativeKind.OPENING: (200, 350, 700),
    NarrativeKind.CONTINUATION: (250, 450, 900),
}
_ROUND_OUTPUT_TOKENS = {"fast": 1024, "expert": 2048, "master": 4096}
_KIND_OUTPUT_TOKENS = {
    NarrativeKind.OPENING: 1024,
    NarrativeKind.CONTINUATION: 1536,
}
_CALL_LIMITS = {
    "fast": (1, 0, 1),
    "expert": (2, 1, 2),
    "master": (3, 2, 2),
}
_DEADLINES = {"fast": 60, "expert": 120, "master": 240}
_EN_WORD_PATTERN = re.compile(r"\b\w+(?:[-'’]\w+)*\b", re.UNICODE)
_LEGACY_GENERATION_BUDGETS = {
    "fast": GenerationBudget("fast", 350, 600, 2048, False, False, 20, 45),
    "expert": GenerationBudget("expert", 800, 1200, 4096, True, True, 45, 90),
    "master": GenerationBudget("master", 1500, 2000, 8192, True, True, 90, 180),
}
_LEGACY_PROMPT_BANDS = {
    NarrativeKind.OPENING: {"zh": (300, 400), "en": (300, 400)},
    NarrativeKind.CONTINUATION: {"zh": (500, 800), "en": (500, 800)},
}


def _normalized_quality(quality_level: str) -> str:
    normalized = str(quality_level or "expert").lower()
    return normalized if normalized in _CALL_LIMITS else "expert"


def _normalized_language(language: str) -> str:
    return "zh" if str(language or "zh").lower().startswith("zh") else "en"


def measure_narrative_length(text: str, language: str) -> int:
    """Measure product length without conflating it with model token usage."""
    if _normalized_language(language) == "zh":
        return sum(1 for character in text if not character.isspace())
    return len(_EN_WORD_PATTERN.findall(text))


def measure_option_length(text: str, language: str) -> int:
    """Measure option copy in the same localized units as narrative copy."""
    return measure_narrative_length(text, language)


def resolve_display_budget(
    language: str,
    *,
    option_call_limit: int = 2,
) -> DisplayBudget:
    """Resolve product and rendering limits for one option group."""
    localized_language = _normalized_language(language)
    if localized_language == "zh":
        target_min, target_max, repair_threshold = 8, 24, 40
        unit: LengthUnit = "characters"
    else:
        target_min, target_max, repair_threshold = 3, 12, 16
        unit = "words"
    return DisplayBudget(
        option_count=3,
        target_min=target_min,
        target_max=target_max,
        repair_threshold=repair_threshold,
        option_call_limit=max(0, option_call_limit),
        max_display_lines=2,
        unit=unit,
    )


def resolve_narrative_budget(
    kind: NarrativeKind | str,
    operation: GenerationOperation | str,
    quality_level: str,
    language: str,
    *,
    original_length: Optional[int] = None,
) -> NarrativeBudget:
    """Resolve one immutable request budget from orthogonal product inputs."""
    resolved_kind = NarrativeKind(kind)
    resolved_operation = GenerationOperation(operation)
    quality = _normalized_quality(quality_level)
    localized_language = _normalized_language(language)
    unit: LengthUnit = "characters" if localized_language == "zh" else "words"

    if resolved_kind == NarrativeKind.ROUND:
        target_min, target_max, compression_threshold = (
            _ZH_ROUND_BANDS[quality]
            if localized_language == "zh"
            else _EN_ROUND_BANDS[quality]
        )
        max_output_tokens = _ROUND_OUTPUT_TOKENS[quality]
    else:
        kind_bands = _ZH_KIND_BANDS if localized_language == "zh" else _EN_KIND_BANDS
        target_min, target_max, compression_threshold = kind_bands[resolved_kind]
        max_output_tokens = _KIND_OUTPUT_TOKENS[resolved_kind]

    base_band = LocalizedLengthBand(
        target_min=target_min,
        target_max=target_max,
        compression_threshold=compression_threshold,
        absolute_max_chars=ABSOLUTE_MAX_NARRATIVE_CHARS,
        unit=unit,
    )

    if resolved_operation == GenerationOperation.REWRITE:
        if original_length is None or original_length < 1:
            raise ValueError("original_length must be positive for rewrite budgets")
        rewrite_min = min(math.floor(original_length * 0.8), compression_threshold)
        rewrite_max = min(math.ceil(original_length * 1.2), compression_threshold)
        base_band = replace(
            base_band,
            target_min=max(1, rewrite_min),
            target_max=max(1, rewrite_max),
        )

    prose_calls, validation_calls, option_calls = _CALL_LIMITS[quality]
    return NarrativeBudget(
        kind=resolved_kind,
        operation=resolved_operation,
        quality_level=quality,
        language=localized_language,
        length=base_band,
        max_output_tokens=max_output_tokens,
        prose_call_limit=prose_calls,
        validation_call_limit=validation_calls,
        option_call_limit=option_calls,
        total_deadline_seconds=_DEADLINES[quality],
    )


def format_length_requirement(budget: NarrativeBudget) -> str:
    """Render the prompt constraint from the same band used for measurement."""
    if budget.length.unit == "characters":
        return f"故事应该{budget.length.target_min}-{budget.length.target_max}字"
    return (
        f"Story should be {budget.length.target_min}-{budget.length.target_max} words"
    )


def resolve_prompt_length_requirement(
    kind: NarrativeKind | str,
    quality_level: str,
    language: str,
    *,
    operation: GenerationOperation | str = GenerationOperation.GENERATE,
    original_length: Optional[int] = None,
) -> str:
    """Resolve prompt wording without duplicating product ranges in templates."""
    from config.feature_flags import get_feature

    resolved_kind = NarrativeKind(kind)
    localized_language = _normalized_language(language)
    if get_feature("unified_narrative_budgets"):
        return format_length_requirement(
            resolve_narrative_budget(
                resolved_kind,
                operation,
                quality_level,
                localized_language,
                original_length=original_length,
            )
        )

    if resolved_kind == NarrativeKind.ROUND:
        return get_generation_budget(quality_level).length_requirement(
            localized_language
        )

    target_min, target_max = _LEGACY_PROMPT_BANDS[resolved_kind][localized_language]
    if localized_language == "zh":
        return f"故事应该{target_min}-{target_max}字"
    return f"Story should be {target_min}-{target_max} words"


def get_generation_budget(level: str) -> GenerationBudget:
    """Return the compatibility round budget for migrated and legacy callers."""
    from config.feature_flags import get_feature

    quality = _normalized_quality(level)
    if not get_feature("unified_narrative_budgets"):
        return _LEGACY_GENERATION_BUDGETS[quality]

    budget = resolve_narrative_budget(
        NarrativeKind.ROUND,
        GenerationOperation.GENERATE,
        quality,
        "zh",
    )
    return GenerationBudget(
        level=quality,
        min_length=budget.length.target_min,
        max_length=budget.length.target_max,
        max_tokens=budget.max_output_tokens,
        allow_quick_regeneration=budget.prose_call_limit > 1,
        allow_ai_consistency=budget.validation_call_limit > 0,
        expected_min_seconds=budget.total_deadline_seconds // 2,
        expected_seconds=budget.total_deadline_seconds,
    )


class GenerationCallTracker:
    """Mutable, request-owned accounting for otherwise immutable budgets."""

    def __init__(
        self,
        budget: NarrativeBudget,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.budget = budget
        self._clock = clock
        self._started_at = clock()
        self.prose_calls = 0
        self.validation_calls = 0
        self.option_calls = 0
        self._recovery_active = False
        self._last_category: Optional[CallCategory] = None

    @property
    def total_calls(self) -> int:
        return self.prose_calls + self.validation_calls + self.option_calls

    @property
    def elapsed_seconds(self) -> float:
        return self._clock() - self._started_at

    @property
    def remaining_seconds(self) -> float:
        """Wall-clock time still available to the whole narrative request."""
        return max(0.0, self.budget.total_deadline_seconds - self.elapsed_seconds)

    def _assert_before_deadline(self) -> None:
        if self.elapsed_seconds >= self.budget.total_deadline_seconds:
            raise GenerationDeadlineExceeded(
                f"Narrative deadline exhausted after {self.elapsed_seconds:.3f}s"
            )

    def assert_before_provider_call(self) -> None:
        """Reject a physical provider call that starts after queueing past deadline."""
        self._assert_before_deadline()

    def consume(self, category: CallCategory) -> int:
        """Consume one allowance before a provider call and return category count."""
        self._assert_before_deadline()
        attributes = {
            "prose": ("prose_calls", self.budget.prose_call_limit),
            "validation": (
                "validation_calls",
                self.budget.validation_call_limit,
            ),
            "option": ("option_calls", self.budget.option_call_limit),
        }
        if category not in attributes:
            raise ValueError(f"Unknown generation call category: {category}")
        attribute, limit = attributes[category]
        current = int(getattr(self, attribute))
        if current >= limit:
            raise GenerationBudgetExceeded(
                f"{category} call allowance exhausted ({current}/{limit})"
            )
        current += 1
        setattr(self, attribute, current)
        self._last_category = category
        return current

    def consume_retry(self) -> int:
        """Charge a provider retry to the category of the preceding call."""
        if self._last_category is None:
            raise GenerationBudgetError(
                "Cannot charge retry before an initial provider call"
            )
        return self.consume(self._last_category)

    @contextmanager
    def recovery_scope(self) -> Iterator[None]:
        """Prevent a continuation response from recursively starting recovery."""
        if self._recovery_active:
            raise RecursiveRecoveryError("Truncation recovery cannot recurse")
        self._recovery_active = True
        try:
            yield
        finally:
            self._recovery_active = False
