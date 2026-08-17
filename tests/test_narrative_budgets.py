"""Contracts for localized narrative budgets and shared call accounting."""

from __future__ import annotations

import pytest

from src.ai.budgets import (GenerationBudgetExceeded, GenerationCallTracker,
                            GenerationDeadlineExceeded, GenerationOperation,
                            NarrativeKind, RecursiveRecoveryError,
                            format_length_requirement,
                            measure_narrative_length, resolve_narrative_budget)
from src.ai.generation_budget import \
    NarrativeKind as CompatibilityNarrativeKind
from src.ai.generation_budget import get_generation_budget

pytestmark = [pytest.mark.unit]



@pytest.mark.parametrize(
    (
        "quality",
        "language",
        "target_min",
        "target_max",
        "compression_threshold",
        "max_output_tokens",
        "deadline",
        "call_limits",
    ),
    [
        ("fast", "zh", 400, 700, 1400, 1024, 60, (1, 0, 1)),
        ("expert", "zh", 800, 1400, 2400, 2048, 120, (3, 2, 2)),
        ("master", "zh", 1200, 2200, 4000, 4096, None, (10, 2, 2)),
        ("fast", "en", 250, 450, 900, 1024, 60, (1, 0, 1)),
        ("expert", "en", 500, 900, 1500, 2048, 120, (3, 2, 2)),
        ("master", "en", 800, 1400, 2500, 4096, None, (10, 2, 2)),
    ],
)
def test_round_budget_defaults_are_localized_and_orthogonal(
    quality: str,
    language: str,
    target_min: int,
    target_max: int,
    compression_threshold: int,
    max_output_tokens: int,
    deadline: int | None,
    call_limits: tuple[int, int, int],
) -> None:
    budget = resolve_narrative_budget(
        NarrativeKind.ROUND,
        GenerationOperation.GENERATE,
        quality,
        language,
    )

    assert (budget.length.target_min, budget.length.target_max) == (
        target_min,
        target_max,
    )
    assert budget.length.compression_threshold == compression_threshold
    assert budget.length.absolute_max_chars == 32_000
    assert budget.max_output_tokens == max_output_tokens
    assert budget.total_deadline_seconds == deadline
    assert (
        budget.prose_call_limit,
        budget.validation_call_limit,
        budget.option_call_limit,
    ) == call_limits


@pytest.mark.parametrize(
    ("kind", "language", "expected"),
    [
        (NarrativeKind.OPENING, "zh", (300, 500, 1000, 1024, "characters")),
        (NarrativeKind.OPENING, "en", (200, 350, 700, 1024, "words")),
        (NarrativeKind.CONTINUATION, "zh", (400, 700, 1400, 1536, "characters")),
        (NarrativeKind.CONTINUATION, "en", (250, 450, 900, 1536, "words")),
    ],
)
def test_opening_and_continuation_have_kind_specific_defaults(
    kind: NarrativeKind,
    language: str,
    expected: tuple[int, int, int, int, str],
) -> None:
    budget = resolve_narrative_budget(
        kind,
        GenerationOperation.GENERATE,
        "master",
        language,
    )

    assert (
        budget.length.target_min,
        budget.length.target_max,
        budget.length.compression_threshold,
        budget.max_output_tokens,
        budget.length.unit,
    ) == expected
    assert budget.total_deadline_seconds is None


def test_rewrite_derives_soft_band_but_keeps_request_execution_budget() -> None:
    budget = resolve_narrative_budget(
        NarrativeKind.ROUND,
        GenerationOperation.REWRITE,
        "expert",
        "zh",
        original_length=2000,
    )

    assert (budget.length.target_min, budget.length.target_max) == (1600, 2400)
    assert budget.max_output_tokens == 2048
    assert budget.prose_call_limit == 3
    assert budget.validation_call_limit == 2
    assert budget.total_deadline_seconds == 120


def test_rewrite_band_never_exceeds_scenario_compression_threshold() -> None:
    budget = resolve_narrative_budget(
        NarrativeKind.ROUND,
        GenerationOperation.REWRITE,
        "fast",
        "en",
        original_length=2000,
    )

    assert (budget.length.target_min, budget.length.target_max) == (900, 900)


def test_regeneration_uses_current_quality_instead_of_original_length() -> None:
    budget = resolve_narrative_budget(
        NarrativeKind.ROUND,
        GenerationOperation.REGENERATE,
        "master",
        "zh",
        original_length=300,
    )

    assert (budget.length.target_min, budget.length.target_max) == (1200, 2200)
    assert budget.max_output_tokens == 4096


def test_localized_measurement_keeps_product_units_separate_from_char_ceiling() -> None:
    assert measure_narrative_length("甲 乙\n丙。", "zh") == 4
    assert measure_narrative_length("Don't split well-known words.", "en") == 4

    budget = resolve_narrative_budget(
        NarrativeKind.ROUND,
        GenerationOperation.GENERATE,
        "expert",
        "en",
    )
    assert budget.exceeds_absolute_limit("a " * 16_001)


def test_prompt_requirement_is_formatted_from_the_resolved_band() -> None:
    zh = resolve_narrative_budget(
        NarrativeKind.OPENING,
        GenerationOperation.GENERATE,
        "fast",
        "zh",
    )
    en = resolve_narrative_budget(
        NarrativeKind.CONTINUATION,
        GenerationOperation.GENERATE,
        "fast",
        "en",
    )

    assert format_length_requirement(zh) == "故事应该300-500字"
    assert format_length_requirement(en) == "Story should be 250-450 words"


def test_call_tracker_consumes_before_overflowing_each_category() -> None:
    budget = resolve_narrative_budget(
        NarrativeKind.ROUND,
        GenerationOperation.GENERATE,
        "expert",
        "zh",
    )
    tracker = GenerationCallTracker(budget)

    assert tracker.consume("prose") == 1
    assert tracker.consume("prose") == 2
    assert tracker.consume("prose") == 3
    with pytest.raises(GenerationBudgetExceeded, match="prose"):
        tracker.consume("prose")
    assert tracker.prose_calls == 3

    assert tracker.consume("validation") == 1
    assert tracker.consume("validation") == 2
    with pytest.raises(GenerationBudgetExceeded, match="validation"):
        tracker.consume("validation")
    assert tracker.validation_calls == 2


@pytest.mark.parametrize("quality,total", [("fast", 2), ("expert", 7), ("master", 14)])
def test_quality_total_call_ceiling_matches_product_contract(quality: str, total: int) -> None:
    budget = resolve_narrative_budget(
        NarrativeKind.ROUND,
        GenerationOperation.GENERATE,
        quality,
        "zh",
    )
    tracker = GenerationCallTracker(budget)

    for _ in range(budget.prose_call_limit):
        tracker.consume("prose")
    for _ in range(budget.validation_call_limit):
        tracker.consume("validation")
    for _ in range(budget.option_call_limit):
        tracker.consume("option")

    assert tracker.total_calls == total


def test_call_tracker_enforces_one_monotonic_deadline() -> None:
    now = [10.0]
    budget = resolve_narrative_budget(
        NarrativeKind.ROUND,
        GenerationOperation.GENERATE,
        "fast",
        "zh",
    )
    tracker = GenerationCallTracker(budget, clock=lambda: now[0])
    now[0] += 60.01

    with pytest.raises(GenerationDeadlineExceeded):
        tracker.consume("prose")
    assert tracker.total_calls == 0


def test_call_tracker_exposes_remaining_total_deadline() -> None:
    now = [10.0]
    budget = resolve_narrative_budget("round", "generate", "expert", "zh")
    tracker = GenerationCallTracker(budget, clock=lambda: now[0])

    now[0] += 25.5

    assert tracker.remaining_seconds == pytest.approx(94.5)


def test_master_call_tracker_has_no_aggregate_deadline() -> None:
    now = [10.0]
    budget = resolve_narrative_budget("round", "generate", "master", "zh")
    tracker = GenerationCallTracker(budget, clock=lambda: now[0])
    now[0] += 10_000

    assert tracker.remaining_seconds is None
    assert tracker.consume("prose") == 1


def test_recovery_scope_rejects_recursive_entry() -> None:
    budget = resolve_narrative_budget(
        NarrativeKind.CONTINUATION,
        GenerationOperation.GENERATE,
        "expert",
        "zh",
    )
    tracker = GenerationCallTracker(budget)

    with tracker.recovery_scope():
        with pytest.raises(RecursiveRecoveryError):
            with tracker.recovery_scope():
                pass


def test_provider_retry_consumes_the_preceding_call_category() -> None:
    tracker = GenerationCallTracker(resolve_narrative_budget("round", "generate", "master", "zh"))

    tracker.consume("validation")
    tracker.consume_retry()

    assert tracker.validation_calls == 2
    assert tracker.prose_calls == 0


def test_provider_retry_cannot_bypass_category_limit() -> None:
    tracker = GenerationCallTracker(resolve_narrative_budget("round", "generate", "fast", "zh"))
    tracker.consume("prose")

    with pytest.raises(GenerationBudgetExceeded):
        tracker.consume_retry()


def test_legacy_budget_import_keeps_flag_off_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "false")

    fast = get_generation_budget("fast")

    assert CompatibilityNarrativeKind is NarrativeKind
    assert (fast.min_length, fast.max_length, fast.max_tokens) == (350, 600, 2048)
    assert fast.allow_quick_regeneration is False
    assert fast.allow_ai_consistency is False


def test_legacy_budget_import_adapts_to_unified_budget_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "true")

    expert = get_generation_budget("expert")

    assert (expert.min_length, expert.max_length, expert.max_tokens) == (
        800,
        1400,
        2048,
    )
    assert expert.allow_quick_regeneration is True
    assert expert.allow_ai_consistency is True
