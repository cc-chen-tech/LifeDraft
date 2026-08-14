"""Authoritative Gregorian timeline for daily-story games."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import re
from typing import Any, Dict, MutableMapping


DAILY_TIMELINE_VERSION = 2
DAILY_TIMELINE_TOTAL_DAYS = 96 * 7
_LEGACY_ROUND_DAY_OFFSETS = (0, 2, 6)


def is_daily_timeline(value: Any) -> bool:
    timeline = getattr(value, "timeline", None)
    if timeline is None and isinstance(value, dict):
        timeline = value.get("timeline")
    return isinstance(timeline, dict) and timeline.get("version") == 2


def _parse_start_date(value: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("start_date must be a valid ISO Gregorian date") from exc


def build_daily_timeline(*, start_date: str, day_index: int) -> Dict[str, Any]:
    """Return the normalized public timeline derived from its two authorities."""
    if isinstance(day_index, bool) or not isinstance(day_index, int) or day_index < 0:
        raise ValueError("day_index must be a non-negative integer")

    parsed_start = _parse_start_date(start_date)
    current = parsed_start + timedelta(days=day_index)
    timeline = {
        "version": DAILY_TIMELINE_VERSION,
        "start_date": parsed_start.isoformat(),
        "current_date": current.isoformat(),
        "day_index": day_index,
        "day_number": min(day_index + 1, DAILY_TIMELINE_TOTAL_DAYS),
        "completed_days": day_index,
        "week_number": day_index // 7 + 1,
        "weekday": current.isoweekday(),
        "total_days": DAILY_TIMELINE_TOTAL_DAYS,
    }
    if day_index >= DAILY_TIMELINE_TOTAL_DAYS:
        timeline["game_over"] = True
    return timeline


def normalize_daily_timeline(value: MutableMapping[str, Any]) -> Dict[str, Any]:
    """Discard derived/stale values and rebuild a timeline from its authorities."""
    return build_daily_timeline(
        start_date=str(value.get("start_date", "")),
        day_index=int(value.get("day_index", 0)),
    )


def advance_daily_timeline(state: MutableMapping[str, Any]) -> Dict[str, Any]:
    """Advance a player mapping by one completed story day."""
    current = normalize_daily_timeline(state["timeline"])
    next_index = min(current["day_index"] + 1, DAILY_TIMELINE_TOTAL_DAYS)
    timeline = build_daily_timeline(
        start_date=current["start_date"], day_index=next_index
    )
    state["timeline"] = timeline

    next_age_day = int(state.get("next_age_day", 365))
    if next_index >= next_age_day:
        state["age"] = int(state.get("age", 0)) + 1
        state["next_age_day"] = next_age_day + 365

    timeline["game_over"] = next_index >= DAILY_TIMELINE_TOTAL_DAYS
    return timeline


def _extract_legacy_era_year(state: MutableMapping[str, Any]) -> int:
    settings = state.get("character_settings")
    era = settings.get("era") if isinstance(settings, dict) else None
    year = era.get("year") if isinstance(era, dict) else None
    if isinstance(year, int) and not isinstance(year, bool) and 1 <= year <= 9999:
        return year
    return 2024


def first_monday_of_year(year: int) -> date:
    """Return the first Gregorian Monday within ``year``."""
    first = date(year, 1, 1)
    return first + timedelta(days=(7 - first.isoweekday() + 1) % 7)


def legacy_position_day_index(week: Any, round_number: Any) -> int:
    """Map a v1 three-round position to its observed daily offset."""
    safe_week = max(0, int(week or 0))
    safe_round = max(0, int(round_number or 0))
    offset = (
        _LEGACY_ROUND_DAY_OFFSETS[safe_round]
        if safe_round < len(_LEGACY_ROUND_DAY_OFFSETS)
        else safe_round
    )
    return safe_week * 7 + offset


def resolve_scheduled_date(current_date: str, phrase: str) -> str:
    """Resolve supported Chinese relative dates against an exact date."""
    current = _parse_start_date(current_date)
    text = str(phrase).strip()
    if text == "明天":
        return (current + timedelta(days=1)).isoformat()
    if text == "后天":
        return (current + timedelta(days=2)).isoformat()
    match = re.fullmatch(r"(\d+)\s*天后", text)
    if match:
        return (current + timedelta(days=int(match.group(1)))).isoformat()

    weekday_names = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
    match = re.fullmatch(r"下周([一二三四五六日天])", text)
    if match:
        days_until_next_monday = 8 - current.isoweekday()
        target = current + timedelta(
            days=days_until_next_monday + weekday_names[match.group(1)] - 1
        )
        return target.isoformat()
    raise ValueError(f"unsupported scheduled date expression: {phrase}")


def migrate_legacy_state(value: MutableMapping[str, Any]) -> Dict[str, Any]:
    """Return an idempotently upgraded copy of a legacy player-state mapping."""
    migrated = deepcopy(dict(value))
    existing_timeline = migrated.get("timeline")
    if isinstance(existing_timeline, dict) and existing_timeline.get("version") == 2:
        migrated["timeline"] = normalize_daily_timeline(existing_timeline)
        return migrated

    start = first_monday_of_year(_extract_legacy_era_year(migrated))
    day_history = []
    latest_completed_index = -1
    for legacy_entry in migrated.get("round_history") or []:
        if not isinstance(legacy_entry, dict):
            continue
        entry = deepcopy(legacy_entry)
        index = legacy_position_day_index(entry.get("week"), entry.get("round"))
        story_date = (start + timedelta(days=index)).isoformat()
        latest_completed_index = max(latest_completed_index, index)
        event_description = str(entry.get("event_description") or "").strip()
        story_continuation = str(entry.get("story_continuation") or "").strip()
        full_story = "\n\n".join(
            part for part in (event_description, story_continuation) if part
        )
        day_history.append(
            {
                "event_id": f"day:{index}",
                "day_index": index,
                "story_date": story_date,
                "event_description": full_story,
                "legacy_event_description": event_description,
                "legacy_story_continuation": story_continuation,
                "options": deepcopy(entry.get("options") or []),
                "choice": entry.get("choice", ""),
                "effects_requested": deepcopy(
                    entry.get("effects_requested") or entry.get("effects") or {}
                ),
                "effects_applied": deepcopy(entry.get("effects") or {}),
                "resource_warnings": deepcopy(entry.get("resource_warnings") or []),
                "summary": entry.get("summary", ""),
                "postprocessing_status": "complete",
                "legacy_week": entry.get("week"),
                "legacy_round": entry.get("round"),
            }
        )

    pending = migrated.get("current_event_data")
    if isinstance(pending, dict):
        current_index = legacy_position_day_index(
            migrated.get("week"), migrated.get("current_round")
        )
        current_event = deepcopy(pending)
        current_event.setdefault("event_id", f"day:{current_index}")
        current_event.setdefault("revision", 1)
        current_event.setdefault(
            "story_date", (start + timedelta(days=current_index)).isoformat()
        )
        migrated["current_event_data"] = current_event
    elif latest_completed_index >= 0:
        current_index = latest_completed_index + 1
    else:
        current_index = legacy_position_day_index(
            migrated.get("week"), migrated.get("current_round")
        )

    migrated["timeline"] = build_daily_timeline(
        start_date=start.isoformat(), day_index=current_index
    )
    migrated["timeline_version"] = DAILY_TIMELINE_VERSION
    migrated["day_history"] = day_history
    for event in migrated.get("scheduled_events") or []:
        if not isinstance(event, dict) or event.get("scheduled_date"):
            continue
        event_index = legacy_position_day_index(
            event.get("scheduled_week"), event.get("scheduled_round")
        )
        event["scheduled_date"] = (start + timedelta(days=event_index)).isoformat()
    completed_age_milestones = current_index // 365
    migrated.setdefault("next_age_day", (completed_age_milestones + 1) * 365)
    return migrated
