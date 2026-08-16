"""Evidence-only detection for daily stories that require world projection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_CLAUSE_BOUNDARY = re.compile(r"[。！？!?；;，,]+")
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


def _clauses(story: str, options: Sequence[Any]) -> tuple[str, ...]:
    source_texts = [str(story or "")]
    source_texts.extend(
        str(option.get("text") if isinstance(option, Mapping) else option or "")
        for option in options
    )
    return tuple(
        clause.strip()
        for text in source_texts
        for clause in _CLAUSE_BOUNDARY.split(text)
        if clause.strip()
    )


def _has_tracked_entity(clause: str, tracked_names: Sequence[str]) -> bool:
    return any(name in clause for name in tracked_names)


def _known_record_terms(tracked_state: Any, keys: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(tracked_state, Mapping):
        return ()
    terms: list[str] = []
    for key in keys:
        records = tracked_state.get(key)
        if isinstance(records, Mapping):
            records = list(records.values())
        if not isinstance(records, (list, tuple)):
            continue
        for record in records:
            values = record.values() if isinstance(record, Mapping) else (record,)
            for value in values:
                if isinstance(value, str) and len(value.strip()) >= 2:
                    terms.append(value.strip())
                elif isinstance(value, (list, tuple)):
                    terms.extend(
                        item.strip()
                        for item in value
                        if isinstance(item, str) and len(item.strip()) >= 2
                    )
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
        tracked_state, ("commitments", "active_commitments")
    )
    known_causal_terms = _known_record_terms(tracked_state, ("causal_chains",))
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

    for clause in _clauses(story, options):
        has_tracked_entity = _has_tracked_entity(clause, tracked_names)
        if has_tracked_entity:
            record("location_updates", _matching_terms(clause, _LOCATION_TERMS))
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
