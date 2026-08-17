"""Deterministic materialization for versioned daily world projections."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Collection, Mapping, Sequence

from src.game.narrative_manager import NarrativeManager
from src.game.world_model_updater import WorldModelUpdater
from src.game.world_projection_schema import WorldPatch, compute_projection_source_hash


logger = logging.getLogger(__name__)


_WORLD_FIELDS = (
    "fact_updates",
    "foreshadowing_seeds",
    "habit_updates",
    "location_updates",
    "career_updates",
    "commitment_updates",
    "causal_updates",
)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _source_identity(projection: Any) -> dict[str, Any]:
    event_id = _field(projection, "event_id")
    revision = _field(projection, "revision")
    day_index = _field(projection, "day_index")
    if (
        not isinstance(event_id, str)
        or not event_id.strip()
        or isinstance(revision, bool)
        or not isinstance(revision, int)
        or revision < 1
        or isinstance(day_index, bool)
        or not isinstance(day_index, int)
        or day_index < 0
    ):
        raise ValueError("invalid_world_projection_identity")
    return {
        "event_id": event_id,
        "revision": revision,
        "day_index": day_index,
    }


def _projection_layer(state: Any) -> dict[str, Any]:
    layer = getattr(state, "world_projection_state", None)
    if not isinstance(layer, dict):
        raise ValueError("invalid_world_projection_state")
    world = layer.get("world")
    if not isinstance(world, dict):
        raise ValueError("invalid_world_projection_world")
    return layer


def initialize_legacy_projection_baseline(
    state: Any, blocked_days: Sequence[int] = ()
) -> bool:
    """Advance only across the contiguous settled prefix created before projections."""

    layer = _projection_layer(state)
    applied = int(layer.get("applied_through_day_index", -1))
    records_by_day: dict[int, list[Mapping[str, Any]]] = {}
    history = getattr(state, "day_history", None)
    if not isinstance(history, list):
        return False
    blocked = {
        day
        for day in blocked_days
        if isinstance(day, int) and not isinstance(day, bool) and day >= 0
    }
    for record in history:
        if not isinstance(record, Mapping):
            continue
        day_index = record.get("day_index")
        if (
            isinstance(day_index, bool)
            or not isinstance(day_index, int)
            or day_index < 0
        ):
            continue
        records_by_day.setdefault(day_index, []).append(record)

    while True:
        if applied + 1 in blocked:
            break
        candidates = records_by_day.get(applied + 1, [])
        if len(candidates) != 1:
            break
        record = candidates[0]
        if "world_projection_status" in record or "world_projection_identity" in record:
            break
        choice_index = record.get("choice_option_index")
        if (
            isinstance(choice_index, bool)
            or not isinstance(choice_index, int)
            or choice_index < 0
        ):
            break
        story = record.get("event_description", record.get("story"))
        if not isinstance(story, str) or not isinstance(record.get("options"), list):
            break
        applied += 1

    previous = int(layer.get("applied_through_day_index", -1))
    if applied == previous:
        return False
    layer["applied_through_day_index"] = applied
    layer["projected_through_day_index"] = max(
        int(layer.get("projected_through_day_index", -1)), applied
    )
    return True


def _record_fingerprint(record: Mapping[str, Any]) -> str:
    value = {key: deepcopy(item) for key, item in record.items() if key != "source"}
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text_list(value: Any) -> bool:
    return isinstance(value, list) and all(_nonempty_text(item) for item in value)


def _valid_materialized_record(category: str, value: Any) -> bool:
    """Keep malformed schema-internal values out of authoritative projection state."""
    if not isinstance(value, Mapping):
        return False
    required_text = {
        "fact_updates": ("subject", "category", "fact"),
        "habit_updates": ("character", "habit"),
        "location_updates": ("character", "location"),
        "career_updates": ("character", "current_job"),
        "commitment_updates": ("description",),
        "causal_updates": ("cause", "expected_consequence"),
        "foreshadowing_seeds": ("description",),
    }
    if not all(_nonempty_text(value.get(field)) for field in required_text[category]):
        return False
    if category == "commitment_updates":
        return _text_list(value.get("parties"))
    if category == "causal_updates" and "characters" in value:
        return _text_list(value.get("characters"))
    if category == "foreshadowing_seeds":
        return _text_list(value.get("related_characters", [])) and _text_list(
            value.get("related_storylines", [])
        )
    return True


def _sanitize_materialized_world(
    world: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    sanitized: dict[str, list[dict[str, Any]]] = {}
    for category in _WORLD_FIELDS:
        records = world.get(category)
        if not isinstance(records, (list, tuple)):
            records = []
        sanitized[category] = [
            deepcopy(dict(record))
            for record in records
            if _valid_materialized_record(category, record)
        ]
    return sanitized


def _attach_provenance(
    current: Sequence[Mapping[str, Any]],
    previous: Sequence[Mapping[str, Any]],
    source: Mapping[str, Any],
) -> list[dict[str, Any]]:
    old_sources: dict[str, list[Any]] = {}
    for record in previous:
        if not isinstance(record, Mapping):
            continue
        fingerprint = _record_fingerprint(record)
        old_sources.setdefault(fingerprint, []).append(deepcopy(record.get("source")))

    materialized: list[dict[str, Any]] = []
    for value in current:
        record = deepcopy(dict(value))
        fingerprint = _record_fingerprint(record)
        candidates = old_sources.get(fingerprint) or []
        old_source = candidates.pop(0) if candidates else None
        record["source"] = (
            old_source if isinstance(old_source, Mapping) else deepcopy(dict(source))
        )
        materialized.append(record)
    return materialized


class _ProjectionStateAdapter:
    """Expose legacy updater fields while owning only the projection layer."""

    def __init__(self, world: Mapping[str, Any], week: int) -> None:
        self.week = week
        self.established_facts = deepcopy(list(world.get("fact_updates") or []))
        self.foreshadowing_seeds = deepcopy(
            list(world.get("foreshadowing_seeds") or [])
        )
        self.character_habits = deepcopy(list(world.get("habit_updates") or []))
        self.pending_storylines: list[dict[str, Any]] = []
        self.foreshadowing_metrics = {"total_planted": 0, "total_expired": 0}
        self.world_model_data = {
            "character_locations": {
                str(record.get("character")): {
                    key: deepcopy(value)
                    for key, value in record.items()
                    if key != "character"
                }
                for record in world.get("location_updates") or []
                if isinstance(record, Mapping) and record.get("character")
            },
            "career_records": {
                str(record.get("character")): {
                    key: deepcopy(value)
                    for key, value in record.items()
                    if key != "character"
                }
                for record in world.get("career_updates") or []
                if isinstance(record, Mapping) and record.get("character")
            },
            "active_commitments": deepcopy(list(world.get("commitment_updates") or [])),
            "causal_chains": deepcopy(list(world.get("causal_updates") or [])),
        }

    def materialized_world(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "fact_updates": deepcopy(self.established_facts),
            "foreshadowing_seeds": deepcopy(self.foreshadowing_seeds),
            "habit_updates": deepcopy(self.character_habits),
            "location_updates": [
                {"character": character, **deepcopy(record)}
                for character, record in self.world_model_data.get(
                    "character_locations", {}
                ).items()
            ],
            "career_updates": [
                {"character": character, **deepcopy(record)}
                for character, record in self.world_model_data.get(
                    "career_records", {}
                ).items()
            ],
            "commitment_updates": deepcopy(
                self.world_model_data.get("active_commitments", [])
            ),
            "causal_updates": deepcopy(self.world_model_data.get("causal_chains", [])),
        }


def _apply_patch(adapter: _ProjectionStateAdapter, patch: WorldPatch) -> None:
    NarrativeManager.process_fact_updates(adapter, patch.fact_updates)
    NarrativeManager.process_foreshadowing_seeds(adapter, patch.foreshadowing_seeds)
    NarrativeManager.process_habit_updates(adapter, patch.habit_updates)
    WorldModelUpdater.process_location_updates(adapter, patch.location_updates)
    WorldModelUpdater.process_career_updates(adapter, patch.career_updates)
    WorldModelUpdater.process_commitment_updates(adapter, patch.commitment_updates)
    WorldModelUpdater.process_causal_updates(adapter, patch.causal_updates)


def apply_world_projection_patch(
    state: Any, projection: Any, option_index: int
) -> bool:
    """Apply one ready projection exactly once to the versioned projection layer."""

    if (
        isinstance(option_index, bool)
        or not isinstance(option_index, int)
        or option_index < 0
    ):
        raise ValueError("invalid_world_projection_option")
    status = str(_field(projection, "status") or "")
    if status not in {"ready", "ready_no_change", "applied"}:
        raise ValueError("world_projection_not_ready")
    source = _source_identity(projection)
    source_hash = _field(projection, "source_hash")
    if not isinstance(source_hash, str) or not source_hash:
        raise ValueError("invalid_world_projection_source_hash")

    layer = _projection_layer(state)
    ledger = layer.setdefault("applied_sources", [])
    for applied in ledger:
        if not isinstance(applied, Mapping) or any(
            applied.get(key) != value for key, value in source.items()
        ):
            continue
        if applied.get("source_hash") != source_hash:
            raise ValueError("world_projection_source_conflict")
        if applied.get("option_index") != option_index:
            raise ValueError("world_projection_option_conflict")
        return False

    current_watermark = int(layer.get("applied_through_day_index", -1))
    if source["day_index"] != current_watermark + 1:
        raise ValueError("world_projection_sequence_gap")

    story_patch = WorldPatch.model_validate(
        _field(projection, "story_patch_json") or {}
    )
    raw_options = _field(projection, "option_patches_json") or {}
    if not isinstance(raw_options, Mapping):
        raise ValueError("invalid_world_projection_option_patches")
    raw_option_patch = raw_options.get(option_index, raw_options.get(str(option_index)))
    if raw_option_patch is None:
        raise ValueError("world_projection_option_missing")
    option_patch = WorldPatch.model_validate(raw_option_patch)

    previous = _sanitize_materialized_world(layer["world"])
    adapter = _ProjectionStateAdapter(previous, int(getattr(state, "week", 0)))
    _apply_patch(adapter, story_patch)
    _apply_patch(adapter, option_patch)
    candidate_world = _sanitize_materialized_world(adapter.materialized_world())
    layer["world"] = {
        category: _attach_provenance(
            candidate_world.get(category, []),
            previous.get(category, []),
            source,
        )
        for category in _WORLD_FIELDS
    }
    ledger.append(
        {
            **source,
            "source_hash": source_hash,
            "option_index": option_index,
        }
    )
    layer["applied_through_day_index"] = source["day_index"]
    layer["projected_through_day_index"] = max(
        int(layer.get("projected_through_day_index", -1)), source["day_index"]
    )
    return True


def _timestamp(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value if isinstance(value, str) else None


def recompute_projection_watermarks(state: Any, rows: Sequence[Any]) -> None:
    """Recompute contiguous ready/applied and pending projection boundaries."""

    layer = _projection_layer(state)
    active = {
        int(_field(row, "day_index")): row
        for row in rows
        if not isinstance(_field(row, "day_index"), bool)
        and isinstance(_field(row, "day_index"), int)
        and str(_field(row, "status") or "") != "superseded"
    }
    applied = int(layer.get("applied_through_day_index", -1))
    while True:
        row = active.get(applied + 1)
        if row is None or str(_field(row, "status") or "") != "applied":
            break
        applied += 1
    layer["applied_through_day_index"] = applied

    projected = applied
    while True:
        row = active.get(projected + 1)
        if row is None or str(_field(row, "status") or "") not in {
            "ready",
            "ready_no_change",
            "applied",
        }:
            break
        projected += 1
    layer["projected_through_day_index"] = projected

    later_days = sorted(day for day in active if day > applied)
    settled_days = [
        record.get("day_index")
        for record in (getattr(state, "day_history", None) or [])
        if isinstance(record, Mapping)
        and isinstance(record.get("day_index"), int)
        and not isinstance(record.get("day_index"), bool)
        and isinstance(record.get("choice_option_index"), int)
        and not isinstance(record.get("choice_option_index"), bool)
    ]
    has_settled_gap = any(day > applied for day in settled_days)
    first_pending = applied + 1 if later_days or has_settled_gap else None
    layer["pending_from_day_index"] = first_pending
    first_row = active.get(first_pending) if first_pending is not None else None
    layer["oldest_pending_at"] = (
        _timestamp(_field(first_row, "created_at")) if first_row is not None else None
    )


def projection_row_snapshot(row: Any) -> Any:
    """Detach the fields needed after a short SQLAlchemy read transaction."""

    return SimpleNamespace(
        projection_id=int(row.projection_id),
        game_id=int(row.game_id),
        event_id=str(row.event_id),
        revision=int(row.revision),
        day_index=int(row.day_index),
        story_date=row.story_date,
        source_hash=str(row.source_hash),
        status=str(row.status),
        story_patch_json=(
            dict(row.story_patch_json)
            if isinstance(row.story_patch_json, Mapping)
            else None
        ),
        option_patches_json=(
            dict(row.option_patches_json)
            if isinstance(row.option_patches_json, Mapping)
            else None
        ),
        created_at=row.created_at,
    )


def _history_record_for_projection(state: Any, row: Any) -> Any:
    matches = [
        record
        for record in (getattr(state, "day_history", None) or [])
        if isinstance(record, dict)
        and record.get("event_id") == row.event_id
        and record.get("revision") == row.revision
        and record.get("day_index") == row.day_index
    ]
    if len(matches) != 1:
        return None
    record = matches[0]
    recorded_id = record.get("world_projection_id")
    if recorded_id is not None and recorded_id != row.projection_id:
        return None
    identity = record.get("world_projection_identity")
    if isinstance(identity, Mapping) and any(
        identity.get(name) != expected
        for name, expected in (
            ("event_id", row.event_id),
            ("revision", row.revision),
            ("day_index", row.day_index),
            ("source_hash", row.source_hash),
        )
    ):
        return None
    story = record.get("event_description", record.get("story", ""))
    options = record.get("options")
    if not isinstance(story, str) or not isinstance(options, list):
        return None
    if compute_projection_source_hash(story, options) != row.source_hash:
        return None
    selected = record.get("choice_option_index")
    if isinstance(selected, bool) or not isinstance(selected, int) or selected < 0:
        return None
    return record


@dataclass(frozen=True)
class ProjectionApplyBatch:
    applied_count: int
    rows_to_mark: tuple[tuple[int, str], ...]
    state_changed: bool


ProjectionOnlyIdentity = tuple[str, int, int, str, int]


def _projection_only_identity(row: Any, selected: int) -> ProjectionOnlyIdentity:
    return (
        row.event_id,
        row.revision,
        row.day_index,
        row.source_hash,
        selected,
    )


def apply_contiguous_world_projections(
    state: Any,
    rows: Sequence[Any],
    projection_only_identities: Collection[ProjectionOnlyIdentity] = (),
) -> ProjectionApplyBatch:
    """Apply the unique settled/ready prefix without crossing any identity gap."""

    by_day: dict[int, list[Any]] = {}
    for row in rows:
        by_day.setdefault(row.day_index, []).append(row)

    applied_count = 0
    rows_to_mark: list[tuple[int, str]] = []
    state_changed = False
    layer = state.world_projection_state
    applied_ledger = layer.get("applied_sources") or []
    applied_through = int(layer.get("applied_through_day_index", -1))
    for row in rows:
        if (
            row.status not in {"ready", "ready_no_change"}
            or row.day_index > applied_through
        ):
            continue
        record = _history_record_for_projection(state, row)
        if record is None:
            continue
        selected = record.get("choice_option_index")
        if any(
            isinstance(source, Mapping)
            and source.get("event_id") == row.event_id
            and source.get("revision") == row.revision
            and source.get("day_index") == row.day_index
            and source.get("source_hash") == row.source_hash
            and source.get("option_index") == selected
            for source in applied_ledger
        ):
            rows_to_mark.append((row.projection_id, row.source_hash))

    while True:
        day_index = int(layer.get("applied_through_day_index", -1)) + 1
        candidates = [
            row for row in by_day.get(day_index, []) if row.status != "superseded"
        ]
        matched = [
            (row, _history_record_for_projection(state, row)) for row in candidates
        ]
        matched = [(row, record) for row, record in matched if record is not None]
        if len(matched) != 1:
            break
        row, record = matched[0]
        if row.status not in {"ready", "ready_no_change", "applied"}:
            break
        selected = int(record["choice_option_index"])
        try:
            changed = apply_world_projection_patch(state, row, selected)
        except Exception:
            # Projection rows are derived and repairable.  A corrupt or
            # incomplete ready payload is a gap, never a reason to reject the
            # already-valid canonical choice being persisted.
            logger.exception(
                "daily world projection materialization deferred "
                "event_id=%s revision=%s day_index=%s",
                row.event_id,
                row.revision,
                row.day_index,
            )
            break
        if _projection_only_identity(row, selected) not in projection_only_identities:
            expected_identity = {
                "event_id": row.event_id,
                "revision": row.revision,
                "day_index": row.day_index,
                "source_hash": row.source_hash,
            }
            if record.get("world_projection_status") != "applied":
                record["world_projection_status"] = "applied"
                state_changed = True
            if record.get("world_projection_id") != row.projection_id:
                record["world_projection_id"] = row.projection_id
                state_changed = True
            if record.get("world_projection_identity") != expected_identity:
                record["world_projection_identity"] = expected_identity
                state_changed = True
        if changed:
            applied_count += 1
            state_changed = True
        if row.status in {"ready", "ready_no_change"}:
            marker = (row.projection_id, row.source_hash)
            if marker not in rows_to_mark:
                rows_to_mark.append(marker)

    before_watermarks = deepcopy(layer)
    recompute_projection_watermarks(state, rows)
    state_changed = state_changed or layer != before_watermarks
    return ProjectionApplyBatch(
        applied_count=applied_count,
        rows_to_mark=tuple(rows_to_mark),
        state_changed=state_changed,
    )
