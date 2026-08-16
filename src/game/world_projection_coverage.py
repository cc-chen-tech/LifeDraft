"""Evidence-only detection for daily stories that require world projection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_SENTENCE_BOUNDARY = re.compile(r"[。！？!?；;]+")
_CLAUSE_BOUNDARY = re.compile(r"[，,]+")
_CONTINUATION_ADVERBS = (
    "此时",
    "这时",
    "这时候",
    "随后",
    "然后",
    "接着",
    "而后",
    "与此同时",
)
_SUBJECTLESS_DIRECTION_PREFIXES = ("向", "对", "把", "在", "从", "往")
_LOCATION_TERMS = (
    "抵达",
    "到达",
    "前往",
    "来到",
    "离开",
    "搬到",
    "返回",
    "回到",
    "赶往",
    "进入",
    "现身",
    "身处",
    "位于",
    "落脚",
    "驻留",
    "当前位置改为",
    "当前位置变为",
    "所在地改为",
    "所在位置变为",
    "位置改为",
)
_FACT_TERMS = ("受伤", "康复", "失去", "获得", "成为", "不再", "状态变为")
_CAREER_TERMS = ("入职", "升职", "晋升", "调任", "辞职", "被解雇", "换了工作")
_HABIT_TERMS = ("养成了", "开始习惯", "不再习惯", "改掉了", "每天都会")
_COMMITMENT_CREATING_TERMS = ("承诺", "约定", "答应")
_COMMITMENT_LIFECYCLE_TERMS = ("兑现", "履行", "完成", "取消", "失约")
_COMMITMENT_EVIDENCE_TERMS = ("承诺", "约定", "任务", "诺言")
_CAUSAL_RESOLUTION_TERMS = ("解决", "化解", "后果", "结果", "因此", "导致")


@dataclass(frozen=True)
class WorldChangeSignals:
    """Matched evidence that extraction should have emitted a non-empty patch."""

    requires_nonempty_patch: bool
    categories: tuple[str, ...]
    matched_spans: tuple[str, ...]


def _tracked_character_names(tracked_state: Any) -> tuple[str, ...]:
    if not isinstance(tracked_state, Mapping):
        return ()
    locations = tracked_state.get("character_locations")
    if not isinstance(locations, Mapping):
        return ()
    return tuple(str(name) for name in locations if str(name).strip())


def _clause_contexts(
    story: str,
    options: Sequence[Any],
    tracked_names: Sequence[str],
) -> tuple[tuple[str, bool], ...]:
    source_texts = [str(story or "")]
    source_texts.extend(
        str(option.get("text") if isinstance(option, Mapping) else option or "")
        for option in options
    )
    contexts: list[tuple[str, bool]] = []
    for text in source_texts:
        for sentence in _SENTENCE_BOUNDARY.split(text):
            active_tracked_subject: str | None = None
            for clause in _CLAUSE_BOUNDARY.split(sentence):
                clause = clause.strip()
                if not clause:
                    continue
                candidate = _normalized_clause_start(clause)
                tracked_subject = _leading_tracked_name(candidate, tracked_names)
                if tracked_subject is not None:
                    active_tracked_subject = tracked_subject
                elif active_tracked_subject and _is_safe_subjectless_continuation(
                    candidate
                ):
                    pass
                else:
                    active_tracked_subject = None
                contexts.append((clause, active_tracked_subject is not None))
    return tuple(contexts)


def _has_tracked_entity(clause: str, tracked_names: Sequence[str]) -> bool:
    return any(name in clause for name in tracked_names)


def _normalized_clause_start(clause: str) -> str:
    candidate = clause.lstrip(" \t、，,；;：:—-")
    while True:
        connector = next(
            (
                prefix
                for prefix in _CONTINUATION_ADVERBS
                if candidate.startswith(prefix)
            ),
            None,
        )
        if connector is None:
            break
        candidate = candidate[len(connector) :].lstrip(" \t、，,；;：:—-")
    return candidate


def _leading_tracked_name(candidate: str, tracked_names: Sequence[str]) -> str | None:
    return next((name for name in tracked_names if candidate.startswith(name)), None)


def _is_safe_subjectless_continuation(candidate: str) -> bool:
    """Allow carry-over only for grammar that explicitly omits a subject."""
    return candidate.startswith(_SUBJECTLESS_DIRECTION_PREFIXES) or any(
        candidate.startswith(term) for term in _LOCATION_TERMS
    )


def _known_record_terms(
    tracked_state: Any,
    keys: Sequence[str],
    content_fields: Sequence[str],
) -> tuple[str, ...]:
    if not isinstance(tracked_state, Mapping):
        return ()
    terms: list[str] = []

    def add_value(value: Any) -> None:
        if isinstance(value, str) and len(value.strip()) >= 2:
            terms.append(value.strip())
        elif isinstance(value, (list, tuple)):
            for item in value:
                add_value(item)

    for key in keys:
        records = tracked_state.get(key)
        if isinstance(records, Mapping):
            records = (
                (records,)
                if any(field in records for field in content_fields)
                else tuple(records.values())
            )
        if not isinstance(records, (list, tuple)):
            continue
        for record in records:
            if isinstance(record, Mapping):
                for field in content_fields:
                    add_value(record.get(field))
            else:
                add_value(record)
    return tuple(dict.fromkeys(terms))


def _matching_terms(clause: str, terms: Sequence[str]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in clause)


def detect_world_change_signals(
    story: str,
    options: Sequence[Any],
    tracked_state: Any = None,
) -> WorldChangeSignals:
    """Return correlated evidence only; this detector never constructs a patch."""
    tracked_names = _tracked_character_names(tracked_state)
    known_commitment_terms = _known_record_terms(
        tracked_state,
        ("commitments", "active_commitments"),
        ("description", "commitment", "task", "content", "details", "terms"),
    )
    known_causal_terms = _known_record_terms(
        tracked_state,
        ("causal_chains",),
        (
            "cause",
            "expected_consequence",
            "consequence",
            "description",
            "resolution",
            "details",
        ),
    )
    categories: list[str] = []
    matches: list[str] = []

    def record(category: str, found: Sequence[str]) -> None:
        if not found:
            return
        if category not in categories:
            categories.append(category)
        for term in found:
            if term not in matches:
                matches.append(term)

    for clause, has_location_subject in _clause_contexts(story, options, tracked_names):
        has_tracked_entity = _has_tracked_entity(clause, tracked_names)
        if has_location_subject:
            record("location_updates", _matching_terms(clause, _LOCATION_TERMS))
        if has_tracked_entity:
            record("fact_updates", _matching_terms(clause, _FACT_TERMS))
            record("career_updates", _matching_terms(clause, _CAREER_TERMS))
            record("habit_updates", _matching_terms(clause, _HABIT_TERMS))

        commitment_terms = _matching_terms(
            clause, _COMMITMENT_CREATING_TERMS + _COMMITMENT_LIFECYCLE_TERMS
        )
        has_commitment_evidence = bool(
            _matching_terms(clause, _COMMITMENT_EVIDENCE_TERMS)
            or _matching_terms(clause, known_commitment_terms)
        )
        if commitment_terms and (
            any(term in _COMMITMENT_CREATING_TERMS for term in commitment_terms)
            or has_commitment_evidence
        ):
            record("commitment_updates", commitment_terms)

        causal_matches = _matching_terms(clause, _CAUSAL_RESOLUTION_TERMS)
        if causal_matches and _matching_terms(clause, known_causal_terms):
            record("causal_updates", causal_matches)

    return WorldChangeSignals(
        requires_nonempty_patch=bool(categories),
        categories=tuple(categories),
        matched_spans=tuple(matches),
    )
