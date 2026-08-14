"""Canonical story-origin validation and compatibility projection."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import re
from typing import Any, Dict, Mapping, Optional, Tuple

from src.game.daily_timeline import build_daily_timeline

_TEXT_FIELDS = ("era_description", "life_stage_description", "world_context")
_ISO_DATE_RE = re.compile(r"(?<!\d)([1-9]\d{3}-\d{1,2}-\d{1,2})(?!\d)")
_ZH_DATE_RE = re.compile(
    r"(?<!\d)([1-9]\d{0,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)
_AGE_RE = re.compile(r"(?<!\d)(\d{1,3})\s*岁")
_EXACT_YEAR_RE = re.compile(r"(?<!\d)([1-9]\d{0,3})\s*年(?!代)")
_ZH_DECADE_RE = re.compile(r"(?<!\d)([1-9]\d{2,3})\s*年代")
_EN_DECADE_RE = re.compile(r"(?<!\d)([1-9]\d{2,3})s\b", re.IGNORECASE)
_EN_AGE_RE = re.compile(
    r"\b(?:age(?:d)?\s*[:=]?\s*)?(\d{1,3})\s*(?:years?\s*old|y/?o)\b",
    re.IGNORECASE,
)
_EN_YEAR_RE = re.compile(r"\b(?:in\s+|year\s*[:=]?\s*)([1-9]\d{2,3})\b", re.IGNORECASE)


class StoryOriginRevisionConflict(ValueError):
    """The draft changed after the caller generated its candidate."""


class StoryOriginLocked(ValueError):
    """The first story day already exists, so chronology is immutable."""


def _parse_gregorian_date(value: Any) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_story_origin_date") from exc


def _explicit_date(value: str) -> Optional[date]:
    matches = [
        (match.start(), "iso", match.groups()) for match in _ISO_DATE_RE.finditer(value)
    ]
    matches.extend(
        (match.start(), "zh", match.groups()) for match in _ZH_DATE_RE.finditer(value)
    )
    if matches:
        _position, kind, groups = max(matches, key=lambda item: item[0])
        if kind == "iso":
            return _parse_gregorian_date(groups[0])
        try:
            return date(*(int(part) for part in groups))
        except ValueError as exc:
            raise ValueError("invalid_story_origin_date") from exc
    return None


def _valid_age(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 120:
        raise ValueError("invalid_story_origin_age")
    return value


def _ordered_int_matches(value: str, *patterns: re.Pattern[str]) -> list[int]:
    matches = [
        (match.start(), int(match.group(1)))
        for pattern in patterns
        for match in pattern.finditer(value)
    ]
    return [number for _position, number in sorted(matches)]


def validate_story_origin(
    value: Mapping[str, Any],
    *,
    explicit_constraints: Optional[str] = None,
    allow_text_time_conflict: bool = False,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("invalid_story_origin")

    revision = value.get("revision", 1)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ValueError("invalid_story_origin_revision")
    parsed_date = _parse_gregorian_date(value.get("start_date"))
    starting_age = _valid_age(value.get("starting_age"))

    normalized: Dict[str, Any] = {
        "revision": revision,
        "start_date": parsed_date.isoformat(),
        "starting_age": starting_age,
    }
    for field in _TEXT_FIELDS:
        text = str(value.get(field) or "").strip()
        if not text:
            raise ValueError(f"invalid_story_origin_{field}")
        normalized[field] = text

    narrative = " ".join(normalized[field] for field in _TEXT_FIELDS)
    narrative_years = set(_ordered_int_matches(narrative, _EXACT_YEAR_RE, _EN_YEAR_RE))
    narrative_decades = set(
        _ordered_int_matches(narrative, _ZH_DECADE_RE, _EN_DECADE_RE)
    )
    if not allow_text_time_conflict and any(
        year != parsed_date.year for year in narrative_years
    ):
        raise ValueError("story_origin_text_time_conflict")
    if not allow_text_time_conflict and any(
        decade != (parsed_date.year // 10) * 10 for decade in narrative_decades
    ):
        raise ValueError("story_origin_text_time_conflict")

    constraints = str(explicit_constraints or "").strip()
    if constraints:
        required_date = _explicit_date(constraints)
        age_matches = _ordered_int_matches(constraints, _AGE_RE, _EN_AGE_RE)
        year_matches = _ordered_int_matches(constraints, _EXACT_YEAR_RE, _EN_YEAR_RE)
        if required_date is not None and parsed_date != required_date:
            raise ValueError("story_origin_feedback_mismatch")
        if (
            required_date is None
            and year_matches
            and parsed_date.year != year_matches[-1]
        ):
            raise ValueError("story_origin_feedback_mismatch")
        if age_matches and starting_age != age_matches[-1]:
            raise ValueError("story_origin_feedback_mismatch")

    return normalized


def project_story_origin(
    settings: Mapping[str, Any],
    origin: Mapping[str, Any],
    *,
    allow_text_time_conflict: bool = False,
) -> Dict[str, Any]:
    normalized_origin = validate_story_origin(
        origin, allow_text_time_conflict=allow_text_time_conflict
    )
    projected = deepcopy(dict(settings))
    start_year = _parse_gregorian_date(normalized_origin["start_date"]).year
    starting_age = normalized_origin["starting_age"]

    # These are read-only compatibility projections, not merge targets. Keeping
    # an old era_name/age_range here can silently reintroduce the chronology the
    # canonical origin replaced.
    era = {
        "year": start_year,
        "era_description": normalized_origin["era_description"],
        "world_context": normalized_origin["world_context"],
    }
    age = {
        "age": starting_age,
        "birth_year": start_year - starting_age,
        "age_description": normalized_origin["life_stage_description"],
    }
    projected["story_origin"] = normalized_origin
    projected["start_date"] = normalized_origin["start_date"]
    projected["era"] = era
    projected["age"] = age
    projected.pop("story_origin_needs_review", None)
    return projected


def normalize_legacy_story_origin(
    settings: Mapping[str, Any],
) -> Tuple[Dict[str, Any], bool]:
    current = settings.get("story_origin")
    if isinstance(current, Mapping):
        return validate_story_origin(current), bool(
            settings.get("story_origin_needs_review", False)
        )

    era = settings.get("era") if isinstance(settings.get("era"), Mapping) else {}
    age = settings.get("age") if isinstance(settings.get("age"), Mapping) else {}

    raw_start = settings.get("start_date")
    if raw_start:
        parsed_start = _parse_gregorian_date(raw_start)
    else:
        raw_year = era.get("year", 2024)
        try:
            era_year = int(raw_year)
        except (TypeError, ValueError):
            era_year = 2024
        if not 1 <= era_year <= 9999:
            era_year = 2024
        parsed_start = date(era_year, 1, 1)

    raw_age = age.get("age", 22)
    try:
        starting_age = int(raw_age)
    except (TypeError, ValueError):
        starting_age = 22
    if not 0 <= starting_age <= 120:
        starting_age = 22

    origin = validate_story_origin(
        {
            "revision": 1,
            "start_date": parsed_start.isoformat(),
            "starting_age": starting_age,
            "era_description": str(
                era.get("era_description") or f"公元{parsed_start.year}年"
            ),
            "life_stage_description": str(age.get("age_description") or "人生新阶段"),
            "world_context": str(era.get("world_context") or "故事开始时的社会环境"),
        },
        allow_text_time_conflict=True,
    )
    narrative = " ".join(
        str(era.get(field) or "")
        for field in ("era_name", "era_description", "world_context")
    )
    explicit_years = {int(match) for match in _EXACT_YEAR_RE.findall(narrative)}
    needs_review = any(year != parsed_start.year for year in explicit_years)
    return origin, needs_review


def normalize_preset_story_origin(settings: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a preset with a canonical origin and compatibility projections."""
    origin, needs_review = normalize_legacy_story_origin(settings)
    normalized = project_story_origin(
        settings, origin, allow_text_time_conflict=needs_review
    )
    if needs_review:
        normalized["story_origin_needs_review"] = True
    return normalized


def canonical_story_settings(settings: Mapping[str, Any]) -> Dict[str, Any]:
    """Use story_origin as the sole chronology source when it is present."""
    current = settings.get("story_origin")
    if isinstance(current, Mapping):
        return project_story_origin(settings, current)
    return deepcopy(dict(settings))


_DEPENDENT_CHARACTER_SETTINGS = {
    "world",
    "family",
    "relationships",
    "traits",
    "appearance",
    "character_image",
    "character_images",
    "personality",
    "personality_traits",
    "narrative_style_id",
}


def story_origin_is_locked(state: Mapping[str, Any]) -> bool:
    timeline = state.get("timeline")
    day_index = timeline.get("day_index", 0) if isinstance(timeline, Mapping) else 0
    return bool(
        int(day_index or 0) > 0
        or state.get("day_history")
        or state.get("current_event_data")
        or state.get("round_history")
        or state.get("story_history")
        or state.get("decision_history")
    )


def rebase_draft_story_origin(
    state: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    expected_revision: int,
) -> Dict[str, Any]:
    """Atomically derive a clean day-zero state from a complete origin candidate.

    This function is intentionally pure. Persistence callers can validate the
    full candidate, then save the returned state before replacing any live
    session or media cache.
    """
    if story_origin_is_locked(state):
        raise StoryOriginLocked("story_origin_locked")

    settings = state.get("character_settings")
    current_settings = deepcopy(dict(settings)) if isinstance(settings, Mapping) else {}
    current_origin, _ = normalize_legacy_story_origin(current_settings)
    if expected_revision != current_origin["revision"]:
        raise StoryOriginRevisionConflict("story_origin_revision_conflict")

    normalized_candidate = validate_story_origin(candidate)
    normalized_candidate["revision"] = current_origin["revision"] + 1

    for key in _DEPENDENT_CHARACTER_SETTINGS:
        current_settings.pop(key, None)
    projected_settings = project_story_origin(current_settings, normalized_candidate)

    updated = deepcopy(dict(state))
    updated["character_settings"] = projected_settings
    updated["age"] = normalized_candidate["starting_age"]
    updated["timeline_version"] = 2
    updated["timeline"] = build_daily_timeline(
        start_date=normalized_candidate["start_date"], day_index=0
    )
    updated["next_age_day"] = 365

    # Every value below is derived from the old origin and must be regenerated.
    updated["relationships"] = {}
    updated["characters"] = {}
    updated["scheduled_events"] = []
    updated["pending_character_introductions"] = []
    updated["narrative_style_id"] = None
    updated["current_event_data"] = None
    updated["resume_view"] = None
    return updated
