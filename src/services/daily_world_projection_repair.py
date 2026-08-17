"""Read-only detection and invariant hashing for daily world projection repair."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

from src.game.world_projection_coverage import detect_world_change_signals


SUSPICIOUS_EMPTY = "suspicious_empty_world_projection"
POSTPROCESSING_STUCK = "postprocessing_pending_or_failed"
WATERMARK_BEHIND = "world_watermark_behind_history"
MISSING_EVENT_RETRYABLE_FAILURE = "missing_current_event_after_retryable_failure"

_WORLD_PATCH_FIELDS = (
    "fact_updates",
    "habit_updates",
    "location_updates",
    "career_updates",
    "commitment_updates",
    "causal_updates",
    "foreshadowing_seeds",
)
_RETRYABLE_FAILURE_CODES = frozenset(
    {"RETRY_EXHAUSTED", "RETRYABLE_FAILURE", "GENERATION_RETRY_EXHAUSTED"}
)


@dataclass(frozen=True)
class RepairReason:
    """A stable machine-readable reason a save needs derived-state repair."""

    code: str
    day_indexes: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "day_indexes": list(self.day_indexes)}


@dataclass(frozen=True)
class GameRepairCandidate:
    """One game selected by the pure scanner, with its exact rebuild range."""

    game_id: int
    reasons: tuple[RepairReason, ...]
    rebuild_day_indexes: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "reasons": [reason.to_dict() for reason in self.reasons],
            "rebuild_day_indexes": list(self.rebuild_day_indexes),
        }


@dataclass(frozen=True)
class RepairScanReport:
    """Deterministically ordered repair candidates for a dry-run/apply handshake."""

    candidates: tuple[GameRepairCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"candidates": [candidate.to_dict() for candidate in self.candidates]}


def _valid_day_index(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _history_records(state: Mapping[str, Any]) -> list[tuple[int, Mapping[str, Any]]]:
    history = state.get("day_history")
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
        return []
    records = [
        (day_index, record)
        for record in history
        if isinstance(record, Mapping)
        and (day_index := _valid_day_index(record.get("day_index"))) is not None
    ]
    return sorted(records, key=lambda item: item[0])


def _world_patch_is_empty(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return True
    return not any(value.get(field) for field in _WORLD_PATCH_FIELDS)


def _recorded_world_patch(record: Mapping[str, Any]) -> tuple[bool, Any]:
    postprocessing = record.get("postprocessing")
    if isinstance(postprocessing, Mapping) and "world" in postprocessing:
        return True, postprocessing.get("world")
    for key in ("world_projection_output", "world_projection", "world_patch"):
        if key in record:
            return True, record.get(key)
    return False, None


def _tracked_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Build the detector's bounded recognition input without changing saved state."""

    legacy = state.get("world_model_data")
    legacy = legacy if isinstance(legacy, Mapping) else {}
    tracked: dict[str, Any] = {
        "character_locations": deepcopy(legacy.get("character_locations") or {}),
        "active_commitments": deepcopy(legacy.get("active_commitments") or []),
        "causal_chains": deepcopy(legacy.get("causal_chains") or []),
    }
    layer = state.get("world_projection_state")
    world = layer.get("world") if isinstance(layer, Mapping) else None
    world = world if isinstance(world, Mapping) else {}
    locations = world.get("location_updates")
    if isinstance(locations, Sequence) and not isinstance(locations, (str, bytes)):
        merged_locations = tracked["character_locations"]
        if not isinstance(merged_locations, dict):
            merged_locations = {}
            tracked["character_locations"] = merged_locations
        for location in locations:
            if not isinstance(location, Mapping):
                continue
            character = location.get("character")
            if isinstance(character, str) and character.strip():
                merged_locations[character] = {
                    key: deepcopy(value)
                    for key, value in location.items()
                    if key not in {"character", "source"}
                }
    for target, source in (
        ("active_commitments", "commitment_updates"),
        ("causal_chains", "causal_updates"),
    ):
        values = world.get(source)
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            tracked[target] = deepcopy(list(values))
    return tracked


def _retryable_generation_failure(state: Mapping[str, Any]) -> bool:
    if state.get("current_event_data") is not None:
        return False
    resume_view = state.get("resume_view")
    if not isinstance(resume_view, Mapping) or resume_view.get("phase") != "failed":
        return False
    failure = resume_view.get("previous_failure") or resume_view.get("failure")
    if isinstance(failure, Mapping):
        if failure.get("retryable") is True:
            return True
        code = str(failure.get("code") or "").upper()
        return code in _RETRYABLE_FAILURE_CODES
    return resume_view.get("retryable") is True


def _projection_watermark(state: Mapping[str, Any]) -> Optional[int]:
    layer = state.get("world_projection_state")
    if not isinstance(layer, Mapping):
        return None
    value = layer.get("applied_through_day_index")
    if isinstance(value, bool) or not isinstance(value, int) or value < -1:
        return -1
    return value


def scan_game_state(
    game_id: int, state: Mapping[str, Any]
) -> Optional[GameRepairCandidate]:
    """Inspect a serialized save without database, network, or mutation side effects."""

    if isinstance(game_id, bool) or not isinstance(game_id, int) or game_id <= 0:
        raise ValueError("invalid_game_id")
    if not isinstance(state, Mapping):
        raise TypeError("game_state_must_be_a_mapping")

    history = _history_records(state)
    tracked_state = _tracked_state(state)
    suspicious_days: list[int] = []
    stuck_days: list[int] = []
    for day_index, record in history:
        status = str(record.get("postprocessing_status") or "")
        if status in {"pending", "failed"}:
            stuck_days.append(day_index)
        if str(record.get("world_projection_status") or "") == "ready_no_change":
            continue
        has_output, world_patch = _recorded_world_patch(record)
        if not has_output or not _world_patch_is_empty(world_patch):
            continue
        signals = detect_world_change_signals(
            str(record.get("event_description") or record.get("story") or ""),
            record.get("options") or [record.get("choice") or ""],
            tracked_state,
        )
        if signals.requires_nonempty_patch:
            suspicious_days.append(day_index)

    history_days = sorted({day_index for day_index, _record in history})
    watermark = _projection_watermark(state)
    watermark_behind = (
        bool(history_days) and watermark is not None and watermark < max(history_days)
    )
    reasons: list[RepairReason] = []
    if suspicious_days:
        reasons.append(
            RepairReason(SUSPICIOUS_EMPTY, tuple(sorted(set(suspicious_days))))
        )
    if stuck_days:
        reasons.append(
            RepairReason(POSTPROCESSING_STUCK, tuple(sorted(set(stuck_days))))
        )
    if watermark_behind:
        reasons.append(
            RepairReason(
                WATERMARK_BEHIND,
                tuple(day for day in history_days if day > int(watermark)),
            )
        )
    if reasons and _retryable_generation_failure(state):
        reasons.append(RepairReason(MISSING_EVENT_RETRYABLE_FAILURE))
    if not reasons:
        return None

    rebuild_days = {
        day for day in history_days if watermark is not None and day > watermark
    }
    rebuild_days.update(suspicious_days)
    rebuild_days.update(stuck_days)
    return GameRepairCandidate(
        game_id=game_id,
        reasons=tuple(reasons),
        rebuild_day_indexes=sorted(rebuild_days),
    )


def build_scan_report(rows: Iterable[GameRepairCandidate]) -> RepairScanReport:
    """Return a report whose candidate and rebuild-day ordering is canonical."""

    raw_candidates = list(rows)
    game_ids = [candidate.game_id for candidate in raw_candidates]
    if len(game_ids) != len(set(game_ids)):
        raise ValueError("duplicate_game_id_in_scan_report")
    normalized = [
        GameRepairCandidate(
            game_id=candidate.game_id,
            reasons=tuple(
                sorted(
                    (
                        RepairReason(
                            reason.code,
                            tuple(sorted(set(reason.day_indexes))),
                        )
                        for reason in candidate.reasons
                    ),
                    key=lambda reason: (reason.code, reason.day_indexes),
                )
            ),
            rebuild_day_indexes=sorted(set(candidate.rebuild_day_indexes)),
        )
        for candidate in raw_candidates
    ]
    candidates = tuple(
        sorted(
            normalized,
            key=lambda candidate: (
                candidate.game_id,
                tuple(candidate.rebuild_day_indexes),
                tuple(reason.code for reason in candidate.reasons),
            ),
        )
    )
    return RepairScanReport(candidates=candidates)


def report_hash(report: RepairScanReport) -> str:
    """Hash a canonical report so dry-run output can fence a later apply."""

    encoded = json.dumps(
        report.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def non_projection_state_digest(state: Mapping[str, Any]) -> str:
    """Hash every saved field except the derived world projection layer."""

    if not isinstance(state, Mapping):
        raise TypeError("game_state_must_be_a_mapping")
    normalized = deepcopy(dict(state))
    normalized.pop("world_projection_state", None)
    encoded = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
