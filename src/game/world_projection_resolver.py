"""Resolve authoritative daily world context from projection watermarks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Mapping, Optional, Sequence

from config.feature_flags import get_feature
from src.ai.long_story_context import DynamicContextParts, LongStoryContextBuilder
from src.game.world_constraint_freshness import WorldConstraintFreshness
from src.game.world_model import WorldModel


_LEGACY_DERIVED_FACT_CATEGORIES = {
    "location",
    "role",
    "career",
    "commitment",
    "causal",
    "cause",
    "consequence",
    "habit",
}


@dataclass(frozen=True)
class ResolvedWorldContext:
    hard_world_model: WorldModel
    soft_context: str
    canonical_tail: str
    freshness: WorldConstraintFreshness


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    return value if isinstance(value, (list, tuple)) else ()


def _valid_day_index(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _projection_world_model_data(layer: Mapping[str, Any]) -> dict[str, Any]:
    world = _mapping(layer.get("world"))
    locations: dict[str, dict[str, Any]] = {}
    careers: dict[str, dict[str, Any]] = {}
    for raw in _sequence(world.get("location_updates")):
        record = _mapping(raw)
        character = str(record.get("character") or "").strip()
        if character:
            locations[character] = {
                key: value
                for key, value in record.items()
                if key not in {"character", "source"}
            }
    for raw in _sequence(world.get("career_updates")):
        record = _mapping(raw)
        character = str(record.get("character") or "").strip()
        if character:
            careers[character] = {
                key: value
                for key, value in record.items()
                if key not in {"character", "source"}
            }
    return {
        "character_locations": locations,
        "career_records": careers,
        "active_commitments": [
            {key: value for key, value in _mapping(raw).items() if key != "source"}
            for raw in _sequence(world.get("commitment_updates"))
            if isinstance(raw, Mapping)
        ],
        "causal_chains": [
            {key: value for key, value in _mapping(raw).items() if key != "source"}
            for raw in _sequence(world.get("causal_updates"))
            if isinstance(raw, Mapping)
        ],
        "physical_states": {},
        "dynamic_facts": [],
        "character_profiles": {},
    }


def _projection_facts(layer: Mapping[str, Any]) -> list[dict[str, Any]]:
    world = _mapping(layer.get("world"))
    return [
        {key: value for key, value in raw.items() if key != "source"}
        for raw in _sequence(world.get("fact_updates"))
        if isinstance(raw, Mapping)
    ]


def _hard_world_model(player_state: Any, layer: Mapping[str, Any]) -> WorldModel:
    base_facts = [
        dict(record)
        for record in _sequence(getattr(player_state, "established_facts", None))
        if isinstance(record, Mapping)
        and str(record.get("category") or "").lower()
        not in _LEGACY_DERIVED_FACT_CATEGORIES
    ]
    projection_facts = _projection_facts(layer)
    hard_facts = [*base_facts, *projection_facts]
    proxy = SimpleNamespace(
        week=int(getattr(player_state, "week", 0) or 0),
        player_name=str(getattr(player_state, "player_name", "") or ""),
        character_settings=dict(
            _mapping(getattr(player_state, "character_settings", None))
        ),
        established_facts=hard_facts,
        world_model_data=_projection_world_model_data(layer),
        continuity_ledger=dict(
            _mapping(getattr(player_state, "continuity_ledger", None))
        ),
    )
    model = WorldModel.from_player_state(proxy)
    model.continuity_source_state = player_state
    model.hard_established_facts = tuple(hard_facts)
    projection_world = _mapping(layer.get("world"))
    model.hard_character_habits = [
        dict(record)
        for record in _sequence(projection_world.get("habit_updates"))
        if isinstance(record, Mapping)
    ]
    return model


def _legacy_soft_context(player_state: Any) -> str:
    legacy_facts = [
        dict(record)
        for record in _sequence(getattr(player_state, "established_facts", None))
        if isinstance(record, Mapping)
        and str(record.get("category") or "").lower() in _LEGACY_DERIVED_FACT_CATEGORIES
    ]
    legacy_world = _mapping(getattr(player_state, "world_model_data", None))
    derived_world = {
        key: legacy_world[key]
        for key in (
            "character_locations",
            "career_records",
            "active_commitments",
            "causal_chains",
        )
        if legacy_world.get(key)
    }
    payload = {
        "world_model_data": derived_world,
        "established_facts": legacy_facts,
        "character_habits": list(
            _sequence(getattr(player_state, "character_habits", None))
        ),
    }
    if not any(payload.values()):
        return ""
    return "【旧世界派生记录（仅供写作提示，不得据此拒绝候选故事）】\n" + json.dumps(
        payload, ensure_ascii=False, sort_keys=True, default=str
    )


def _actual_choice(record: Mapping[str, Any]) -> str:
    explicit = str(record.get("choice") or "").strip()
    if explicit:
        return explicit
    option_index = record.get("choice_option_index")
    options = record.get("options")
    if (
        isinstance(option_index, int)
        and not isinstance(option_index, bool)
        and isinstance(options, list)
        and 0 <= option_index < len(options)
    ):
        option = options[option_index]
        if isinstance(option, Mapping):
            return str(option.get("text") or "").strip()
        return str(option or "").strip()
    return ""


def _tail_record(record: Mapping[str, Any]) -> str:
    day_index = _valid_day_index(record.get("day_index"))
    event_id = str(record.get("event_id") or "").strip()
    revision = record.get("revision")
    date = str(
        record.get("story_date")
        or record.get("date")
        or _mapping(record.get("date_info")).get("date_string")
        or ""
    ).strip()
    story = str(
        record.get("event_description")
        or record.get("story_text")
        or record.get("full_story")
        or ""
    ).strip()
    choice = _actual_choice(record)
    identity = [f"day_index={day_index}" if day_index is not None else ""]
    if event_id:
        identity.append(f"event_id={event_id}")
    if isinstance(revision, int) and not isinstance(revision, bool):
        identity.append(f"revision={revision}")
    if date:
        identity.append(f"date={date}")
    lines = ["[ACCEPTED_DAY " + " ".join(item for item in identity if item) + "]"]
    if story:
        lines.append("已接受故事：" + story)
    if choice:
        lines.append("玩家选择：" + choice)
    return "\n".join(lines)


def _record_identity(record: Mapping[str, Any]) -> tuple[Any, ...]:
    event_id = str(record.get("event_id") or "").strip()
    revision = record.get("revision")
    if event_id:
        return ("event", event_id, revision)
    return (
        "fallback",
        _valid_day_index(record.get("day_index")),
        str(record.get("story_date") or record.get("date") or ""),
        str(record.get("event_description") or record.get("story_text") or ""),
    )


def _canonical_tail(
    player_state: Any, applied_through: int
) -> tuple[str, Optional[int]]:
    records = [
        record
        for record in _sequence(getattr(player_state, "day_history", None))
        if isinstance(record, Mapping)
    ]
    current = getattr(player_state, "current_event_data", None)
    if isinstance(current, Mapping):
        current_record = dict(current)
        if _valid_day_index(current_record.get("day_index")) is None:
            timeline = _mapping(getattr(player_state, "timeline", None))
            current_record["day_index"] = timeline.get("day_index")
        if not current_record.get("story_date"):
            timeline = _mapping(getattr(player_state, "timeline", None))
            current_record["story_date"] = timeline.get("current_date")
        records.append(current_record)

    eligible = []
    for record in records:
        day_index = _valid_day_index(record.get("day_index"))
        if day_index is not None and day_index > applied_through:
            eligible.append(record)
    eligible.sort(
        key=lambda record: (
            _valid_day_index(record.get("day_index"))
            if _valid_day_index(record.get("day_index")) is not None
            else -1
        )
    )
    seen: set[tuple[Any, ...]] = set()
    blocks: list[str] = []
    block_days: list[Optional[int]] = []
    for record in eligible:
        identity = _record_identity(record)
        if identity in seen:
            continue
        seen.add(identity)
        block = _tail_record(record)
        blocks.append(block)
        block_days.append(_valid_day_index(record.get("day_index")))

    rendered = (
        LongStoryContextBuilder()
        .fit_dynamic_context(
            DynamicContextParts(current_request="", recent_events=blocks)
        )
        .strip()
    )
    first_day = next(
        (day for block, day in zip(blocks, block_days) if block in rendered),
        None,
    )
    return rendered, first_day


def resolve_world_context(player_state: Any) -> ResolvedWorldContext:
    """Resolve hard projection facts, soft legacy hints, and the ledger tail."""

    if not get_feature("daily_world_projection_v1"):
        from src.game.world_constraint_freshness import (
            build_legacy_validation_world_model,
        )

        legacy = build_legacy_validation_world_model(player_state)
        return ResolvedWorldContext(
            hard_world_model=legacy.world_model,
            soft_context=legacy.soft_context,
            canonical_tail="",
            freshness=legacy.freshness,
        )

    layer = _mapping(getattr(player_state, "world_projection_state", None))
    applied = layer.get("applied_through_day_index", -1)
    if isinstance(applied, bool) or not isinstance(applied, int) or applied < -1:
        applied = -1
    canonical_tail, first_tail_day = _canonical_tail(player_state, applied)
    pending_from = _valid_day_index(layer.get("pending_from_day_index"))
    if pending_from is not None and pending_from <= applied:
        pending_from = None
    stale_from = pending_from if pending_from is not None else first_tail_day
    freshness = WorldConstraintFreshness(
        stale_from_day_index=stale_from,
        reason="world_projection_watermark_lag" if stale_from is not None else None,
    )
    return ResolvedWorldContext(
        hard_world_model=_hard_world_model(player_state, layer),
        soft_context=_legacy_soft_context(player_state),
        canonical_tail=canonical_tail,
        freshness=freshness,
    )
