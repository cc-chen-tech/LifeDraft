"""Resolve authoritative daily world context from projection watermarks."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Mapping, Optional, Sequence

from config.feature_flags import get_feature
from src.ai.long_story_context import DynamicContextParts, LongStoryContextBuilder
from src.game.world_constraint_freshness import WorldConstraintFreshness
from src.game.world_model import WorldModel


_IMMUTABLE_BASE_FACT_CATEGORIES = {
    "identity",
    "immutable_identity",
    "base_identity",
    "origin",
    "birth",
    "species",
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


def _text(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _text_list(value: Any) -> Optional[list[str]]:
    if not isinstance(value, list):
        return None
    result = []
    for item in value:
        text = _text(item)
        if text is None:
            return None
        result.append(text)
    return result


def _is_immutable_base_fact(record: Mapping[str, Any]) -> bool:
    return str(record.get("category") or "").lower() in (
        _IMMUTABLE_BASE_FACT_CATEGORIES
    )


@dataclass
class _ProjectionContextData:
    world_model_data: dict[str, Any]
    facts: list[dict[str, Any]]
    habits: list[dict[str, Any]]
    foreshadowing_seeds: list[dict[str, Any]]
    soft_world: dict[str, list[dict[str, Any]]]


def _projection_context_data(
    layer: Mapping[str, Any], *, mutable_is_hard: bool
) -> _ProjectionContextData:
    world = _mapping(layer.get("world"))
    locations: dict[str, dict[str, Any]] = {}
    careers: dict[str, dict[str, Any]] = {}
    commitments: list[dict[str, Any]] = []
    causal_chains: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    habits: list[dict[str, Any]] = []
    seeds: list[dict[str, Any]] = []
    soft_world: dict[str, list[dict[str, Any]]] = {}

    def soften(category: str, raw: Any) -> None:
        if isinstance(raw, Mapping):
            soft_world.setdefault(category, []).append(deepcopy(dict(raw)))

    for raw in _sequence(world.get("location_updates")):
        record = _mapping(raw)
        character = _text(record.get("character"))
        location = _text(record.get("location"))
        if not mutable_is_hard or character is None or location is None:
            soften("location_updates", raw)
            continue
        locations[character] = {
            "location": location,
            "region": _text(record.get("region")) or "",
            "since_week": (
                record.get("since_week")
                if isinstance(record.get("since_week"), int)
                and not isinstance(record.get("since_week"), bool)
                else 0
            ),
            "travel_mode": _text(record.get("travel_mode")) or "resident",
        }
    for raw in _sequence(world.get("career_updates")):
        record = _mapping(raw)
        character = _text(record.get("character"))
        job = _text(record.get("current_job"))
        if not mutable_is_hard or character is None or job is None:
            soften("career_updates", raw)
            continue
        careers[character] = {
            "current_job": job,
            "employer": _text(record.get("employer")) or "",
            "level": _text(record.get("level")) or "mid",
            "since_week": (
                record.get("since_week")
                if isinstance(record.get("since_week"), int)
                and not isinstance(record.get("since_week"), bool)
                else 0
            ),
            "history": (
                record.get("history") if isinstance(record.get("history"), list) else []
            ),
        }
    for raw in _sequence(world.get("commitment_updates")):
        record = _mapping(raw)
        description = _text(record.get("description"))
        parties = _text_list(record.get("parties"))
        if not mutable_is_hard or description is None or parties is None:
            soften("commitment_updates", raw)
            continue
        commitments.append(
            {
                "description": description,
                "parties": parties,
                "deadline_week": (
                    record.get("deadline_week")
                    if isinstance(record.get("deadline_week"), int)
                    and not isinstance(record.get("deadline_week"), bool)
                    else -1
                ),
                "status": _text(record.get("status")) or "pending",
                "created_week": (
                    record.get("created_week")
                    if isinstance(record.get("created_week"), int)
                    and not isinstance(record.get("created_week"), bool)
                    else 0
                ),
                "importance": _text(record.get("importance")) or "normal",
            }
        )
    for raw in _sequence(world.get("causal_updates")):
        record = _mapping(raw)
        cause = _text(record.get("cause"))
        consequence = _text(record.get("expected_consequence"))
        characters = _text_list(record.get("characters", []))
        if (
            not mutable_is_hard
            or cause is None
            or consequence is None
            or characters is None
        ):
            soften("causal_updates", raw)
            continue
        causal_chains.append(
            {
                "cause": cause,
                "expected_consequence": consequence,
                "characters": characters,
                "created_week": (
                    record.get("created_week")
                    if isinstance(record.get("created_week"), int)
                    and not isinstance(record.get("created_week"), bool)
                    else 0
                ),
                "resolved": (
                    record.get("resolved")
                    if isinstance(record.get("resolved"), bool)
                    else False
                ),
            }
        )
    for raw in _sequence(world.get("fact_updates")):
        record = _mapping(raw)
        valid = all(
            _text(record.get(field)) is not None
            for field in ("subject", "category", "fact")
        )
        if not valid or (not mutable_is_hard and not _is_immutable_base_fact(record)):
            soften("fact_updates", raw)
            continue
        facts.append(
            {key: deepcopy(value) for key, value in record.items() if key != "source"}
        )
    for raw in _sequence(world.get("habit_updates")):
        record = _mapping(raw)
        if (
            not mutable_is_hard
            or _text(record.get("character")) is None
            or _text(record.get("habit")) is None
        ):
            soften("habit_updates", raw)
            continue
        habits.append(deepcopy(dict(record)))
    for raw in _sequence(world.get("foreshadowing_seeds")):
        record = _mapping(raw)
        valid = (
            mutable_is_hard
            and isinstance(raw, dict)
            and _text(record.get("description")) is not None
            and isinstance(record.get("planted_week", 0), int)
            and not isinstance(record.get("planted_week", 0), bool)
            and isinstance(record.get("maturity_weeks", 8), int)
            and not isinstance(record.get("maturity_weeks", 8), bool)
            and isinstance(record.get("obfuscation_level", 0.5), (int, float))
            and not isinstance(record.get("obfuscation_level", 0.5), bool)
            and _text_list(record.get("related_characters", [])) is not None
            and _text_list(record.get("related_storylines", [])) is not None
        )
        if not valid:
            soften("foreshadowing_seeds", raw)
            continue
        seeds.append(raw)

    return _ProjectionContextData(
        world_model_data={
            "character_locations": locations,
            "career_records": careers,
            "active_commitments": commitments,
            "causal_chains": causal_chains,
            "physical_states": {},
            "dynamic_facts": [],
            "character_profiles": {},
        },
        facts=facts,
        habits=habits,
        foreshadowing_seeds=seeds,
        soft_world=soft_world,
    )


def _hard_world_model(
    player_state: Any,
    projection: _ProjectionContextData,
) -> WorldModel:
    base_facts = [
        dict(record)
        for record in _sequence(getattr(player_state, "established_facts", None))
        if isinstance(record, Mapping) and _is_immutable_base_fact(record)
    ]
    hard_facts = [*base_facts, *projection.facts]
    character_settings = deepcopy(
        dict(_mapping(getattr(player_state, "character_settings", None)))
    )
    occupation = _mapping(character_settings.pop("occupation", None))
    background = _mapping(character_settings.pop("background", None))
    initial_roles = {
        value
        for value in (
            _text(occupation.get("occupation") or occupation.get("role")),
            _text(background.get("occupation") or background.get("role")),
        )
        if value
    }
    continuity_ledger = deepcopy(
        dict(_mapping(getattr(player_state, "continuity_ledger", None)))
    )
    continuity_ledger["mutable_states"] = {
        "health": {},
        "relationships": {},
        "facts": {},
    }
    identities = _mapping(continuity_ledger.get("immutable_identities"))
    player_name = str(getattr(player_state, "player_name", "") or "")
    player_identity = identities.get(player_name)
    if isinstance(player_identity, Mapping) and initial_roles:
        cleaned_identity = deepcopy(dict(player_identity))
        cleaned_identity["roles"] = [
            role
            for role in _sequence(player_identity.get("roles"))
            if role not in initial_roles
        ]
        continuity_ledger["immutable_identities"] = {
            **dict(identities),
            player_name: cleaned_identity,
        }
    proxy = SimpleNamespace(
        week=int(getattr(player_state, "week", 0) or 0),
        age=getattr(player_state, "age", None),
        player_name=player_name,
        character_settings=character_settings,
        established_facts=hard_facts,
        world_model_data=projection.world_model_data,
        continuity_ledger=continuity_ledger,
        round_history=getattr(player_state, "round_history", None) or [],
    )
    model = WorldModel.from_player_state(proxy)
    model.continuity_source_state = player_state
    model.hard_established_facts = tuple(hard_facts)
    model.hard_character_habits = projection.habits
    model.hard_foreshadowing_seeds = projection.foreshadowing_seeds
    return model


def _soft_context(
    player_state: Any,
    projection_soft_world: Mapping[str, Any],
) -> str:
    legacy_facts = [
        dict(record)
        for record in _sequence(getattr(player_state, "established_facts", None))
        if isinstance(record, Mapping) and not _is_immutable_base_fact(record)
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
    character_settings = _mapping(getattr(player_state, "character_settings", None))
    legacy_occupation = _mapping(character_settings.get("occupation"))
    legacy_ledger = _mapping(getattr(player_state, "continuity_ledger", None))
    legacy_mutable_states = _mapping(legacy_ledger.get("mutable_states"))
    payload = {
        "world_model_data": derived_world,
        "established_facts": legacy_facts,
        "character_habits": list(
            _sequence(getattr(player_state, "character_habits", None))
        ),
        "initial_occupation": dict(legacy_occupation),
        "continuity_ledger_mutable_states": deepcopy(dict(legacy_mutable_states)),
        "stale_or_invalid_projection_world": dict(projection_soft_world),
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

    admitted = LongStoryContextBuilder().fit_dynamic_context(
        DynamicContextParts(current_request="", recent_events=list(reversed(blocks)))
    )
    selected = {
        index
        for index, block in enumerate(blocks)
        if f"[RECENT_EVENT]\n{block}\n" in admitted
    }
    rendered = "".join(
        f"[RECENT_EVENT]\n{block}\n"
        for index, block in enumerate(blocks)
        if index in selected
    ).strip()
    first_eligible_day = next((day for day in block_days if day is not None), None)
    return rendered, first_eligible_day


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
    projection = _projection_context_data(
        layer,
        mutable_is_hard=stale_from is None,
    )
    return ResolvedWorldContext(
        hard_world_model=_hard_world_model(player_state, projection),
        soft_context=_soft_context(player_state, projection.soft_world),
        canonical_tail=canonical_tail,
        freshness=freshness,
    )
