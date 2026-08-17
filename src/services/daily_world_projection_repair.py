"""Read-only detection and invariant hashing for daily world projection repair."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from sqlalchemy import and_, func

from src.database.models import (
    DailyWorldProjection,
    DailyWorldProjectionRepairAudit,
    GameState,
    SessionLocal,
)
from src.game.state.player_data import default_world_projection_state
from src.game.world_projection_coverage import detect_world_change_signals
from src.game.world_projection_schema import compute_projection_source_hash
from src.services.daily_world_projection_repository import ProjectionIdentity


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
    state_id: Optional[int] = None
    non_projection_digest: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "reasons": [reason.to_dict() for reason in self.reasons],
            "rebuild_day_indexes": list(self.rebuild_day_indexes),
            "state_id": self.state_id,
            "non_projection_digest": self.non_projection_digest,
        }


@dataclass(frozen=True)
class RepairScanReport:
    """Deterministically ordered repair candidates for a dry-run/apply handshake."""

    candidates: tuple[GameRepairCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"candidates": [candidate.to_dict() for candidate in self.candidates]}

    @property
    def hash(self) -> str:
        return report_hash(self)


@dataclass(frozen=True)
class RebuildIdentity:
    """One accepted-history source rebuilt by the durable projection worker."""

    event_id: str
    revision: int
    day_index: int
    source_hash: str
    story_date: Optional[str] = None
    selected_option_index: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "event_id": self.event_id,
            "revision": self.revision,
            "day_index": self.day_index,
            "source_hash": self.source_hash,
        }
        if self.selected_option_index is not None:
            value["selected_option_index"] = self.selected_option_index
        return value

    @property
    def projection_key(self) -> tuple[str, int, int, str]:
        return (self.event_id, self.revision, self.day_index, self.source_hash)


@dataclass(frozen=True)
class RepairVerification:
    """Read-only result of checking one queued repair audit."""

    status: str
    non_projection_digest_after: str
    detail: str = ""


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

    rebuild_days = (
        set(history_days)
        if watermark is None
        else {day for day in history_days if day > watermark}
    )
    rebuild_days.update(suspicious_days)
    rebuild_days.update(stuck_days)
    return GameRepairCandidate(
        game_id=game_id,
        reasons=tuple(reasons),
        rebuild_day_indexes=sorted(rebuild_days),
        non_projection_digest=non_projection_state_digest(state),
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
            state_id=candidate.state_id,
            non_projection_digest=candidate.non_projection_digest,
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


def scan_latest_game_states(
    session_factory: Callable[[], Any] = SessionLocal,
    *,
    game_id: Optional[int] = None,
) -> RepairScanReport:
    """Read only the latest persisted snapshot for each selected game."""

    with session_factory() as db:
        latest = (
            db.query(
                GameState.game_id.label("game_id"),
                func.max(GameState.state_id).label("state_id"),
            )
            .group_by(GameState.game_id)
            .subquery()
        )
        query = db.query(GameState).join(
            latest,
            and_(
                GameState.game_id == latest.c.game_id,
                GameState.state_id == latest.c.state_id,
            ),
        )
        if game_id is not None:
            query = query.filter(GameState.game_id == game_id)
        rows = query.order_by(GameState.game_id).all()
        candidates: list[GameRepairCandidate] = []
        for row in rows:
            state = row.state_json
            if not isinstance(state, Mapping):
                continue
            candidate = scan_game_state(int(row.game_id), state)
            if candidate is None:
                continue
            if _candidate_already_materialized(db, candidate, state):
                continue
            candidates.append(
                GameRepairCandidate(
                    game_id=candidate.game_id,
                    reasons=candidate.reasons,
                    rebuild_day_indexes=candidate.rebuild_day_indexes,
                    state_id=int(row.state_id),
                    non_projection_digest=non_projection_state_digest(state),
                )
            )
        return build_scan_report(candidates)


def _candidate_already_materialized(
    db: Any, candidate: GameRepairCandidate, state: Mapping[str, Any]
) -> bool:
    """Suppress legacy failure markers after their exact sources are rebuilt."""

    try:
        identities = rebuild_identities(candidate, state)
    except ValueError:
        return False
    if not identities:
        return False
    layer = state.get("world_projection_state")
    max_day = max(identity.day_index for identity in identities)
    if not isinstance(layer, Mapping) or any(
        not isinstance(layer.get(name), int)
        or isinstance(layer.get(name), bool)
        or int(layer[name]) < max_day
        for name in (
            "applied_through_day_index",
            "projected_through_day_index",
        )
    ):
        return False
    applied_sources = layer.get("applied_sources")
    source_keys = {
        (
            source.get("event_id"),
            source.get("revision"),
            source.get("day_index"),
            source.get("source_hash"),
        )
        for source in (applied_sources if isinstance(applied_sources, list) else [])
        if isinstance(source, Mapping)
    }
    if any(identity.projection_key not in source_keys for identity in identities):
        return False
    for identity in identities:
        count = (
            db.query(DailyWorldProjection)
            .filter(
                DailyWorldProjection.game_id == candidate.game_id,
                DailyWorldProjection.event_id == identity.event_id,
                DailyWorldProjection.revision == identity.revision,
                DailyWorldProjection.day_index == identity.day_index,
                DailyWorldProjection.source_hash == identity.source_hash,
                DailyWorldProjection.status == "applied",
            )
            .count()
        )
        if count != 1:
            return False
    return True


def rebuild_identities(
    candidate: GameRepairCandidate, state: Mapping[str, Any]
) -> tuple[RebuildIdentity, ...]:
    """Validate and freeze accepted sources in strict oldest-first order."""

    requested_days = set(candidate.rebuild_day_indexes)
    records_by_day: dict[int, list[Mapping[str, Any]]] = {}
    for day_index, record in _history_records(state):
        if day_index in requested_days:
            records_by_day.setdefault(day_index, []).append(record)

    identities: list[RebuildIdentity] = []
    for day_index in sorted(requested_days):
        records = records_by_day.get(day_index) or []
        if len(records) != 1:
            raise ValueError(f"repair_history_identity_ambiguous day_index={day_index}")
        record = records[0]
        event_id = record.get("event_id")
        revision = record.get("revision", 1)
        story = record.get("event_description", record.get("story"))
        options = record.get("options")
        selected = record.get("choice_option_index")
        if (
            not isinstance(event_id, str)
            or not event_id.strip()
            or isinstance(revision, bool)
            or not isinstance(revision, int)
            or revision < 1
            or not isinstance(story, str)
            or not story.strip()
            or not isinstance(options, list)
            or not options
            or isinstance(selected, bool)
            or not isinstance(selected, int)
            or selected < 0
            or selected >= len(options)
        ):
            raise ValueError(f"repair_history_identity_invalid day_index={day_index}")
        story_date = record.get("story_date")
        identities.append(
            RebuildIdentity(
                event_id=event_id,
                revision=revision,
                day_index=day_index,
                source_hash=compute_projection_source_hash(story, options),
                story_date=story_date if isinstance(story_date, str) else None,
                selected_option_index=selected,
            )
        )
    return tuple(identities)


def enqueue_rebuild(
    candidate: GameRepairCandidate, repo: Any, state: Mapping[str, Any]
) -> tuple[RebuildIdentity, ...]:
    """Ensure one ordinary fenced projection row per accepted repair source."""

    identities = rebuild_identities(candidate, state)
    for identity in identities:
        repo.ensure_projection(
            ProjectionIdentity(
                game_id=candidate.game_id,
                event_id=identity.event_id,
                revision=identity.revision,
                day_index=identity.day_index,
                story_date=identity.story_date,
            ),
            identity.source_hash,
        )
    return identities


def initialized_projection_state(
    state: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Preserve a structurally valid v1 layer or supply isolated defaults."""

    layer = state.get("world_projection_state")
    valid = (
        isinstance(layer, Mapping)
        and layer.get("version") == 1
        and isinstance(layer.get("world"), Mapping)
        and isinstance(layer.get("applied_sources"), list)
        and _valid_watermark(layer.get("applied_through_day_index"))
        and _valid_watermark(layer.get("projected_through_day_index"))
    )
    return (
        deepcopy(dict(layer)) if valid else default_world_projection_state(),
        not valid,
    )


def verify_repair_invariants(
    session_factory: Callable[[], Any], audit_id: int
) -> RepairVerification:
    """Check source fences, contiguous watermarks, and the visible-state digest."""

    with session_factory() as db:
        audit = db.get(DailyWorldProjectionRepairAudit, audit_id)
        if audit is None:
            raise ValueError("repair_audit_not_found")
        latest = (
            db.query(GameState)
            .filter(GameState.game_id == audit.game_id)
            .order_by(GameState.state_id.desc())
            .first()
        )
        if latest is None or not isinstance(latest.state_json, Mapping):
            return RepairVerification("failed_invariant", "", "latest_state_missing")
        digest_after = non_projection_state_digest(latest.state_json)
        if digest_after != audit.non_projection_digest_before:
            return RepairVerification(
                "failed_invariant", digest_after, "non_projection_state_changed"
            )
        identities = audit_rebuild_identities(audit.detail_json)
        if not identities:
            return RepairVerification(
                "failed_invariant", digest_after, "rebuild_identities_missing"
            )
        rows: list[DailyWorldProjection] = []
        for identity in identities:
            row = (
                db.query(DailyWorldProjection)
                .filter(
                    DailyWorldProjection.game_id == audit.game_id,
                    DailyWorldProjection.event_id == identity.event_id,
                    DailyWorldProjection.revision == identity.revision,
                    DailyWorldProjection.day_index == identity.day_index,
                    DailyWorldProjection.source_hash == identity.source_hash,
                )
                .one_or_none()
            )
            if row is None:
                replacement = (
                    db.query(DailyWorldProjection)
                    .filter(
                        DailyWorldProjection.game_id == audit.game_id,
                        DailyWorldProjection.event_id == identity.event_id,
                        DailyWorldProjection.revision == identity.revision,
                    )
                    .one_or_none()
                )
                if replacement is not None:
                    return RepairVerification(
                        "fenced", digest_after, "projection_source_replaced"
                    )
                return RepairVerification("pending", digest_after, "projection_missing")
            rows.append(row)
        if any(row.status == "superseded" for row in rows):
            return RepairVerification("fenced", digest_after, "projection_superseded")
        if any(row.status != "applied" for row in rows):
            return RepairVerification("pending", digest_after, "projection_pending")

        layer = latest.state_json.get("world_projection_state")
        max_day = max(identity.day_index for identity in identities)
        if not isinstance(layer, Mapping) or any(
            not isinstance(layer.get(name), int)
            or isinstance(layer.get(name), bool)
            or int(layer[name]) < max_day
            for name in (
                "applied_through_day_index",
                "projected_through_day_index",
            )
        ):
            return RepairVerification("pending", digest_after, "watermark_incomplete")
        applied_sources = layer.get("applied_sources")
        source_keys = {
            (
                source.get("event_id"),
                source.get("revision"),
                source.get("day_index"),
                source.get("source_hash"),
            )
            for source in (applied_sources if isinstance(applied_sources, list) else [])
            if isinstance(source, Mapping)
        }
        if any(identity.projection_key not in source_keys for identity in identities):
            return RepairVerification(
                "pending", digest_after, "source_ledger_incomplete"
            )
        return RepairVerification("complete", digest_after)


def _valid_watermark(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= -1


def audit_rebuild_identities(value: Any) -> tuple[RebuildIdentity, ...]:
    """Parse only complete source-fenced identities from durable audit metadata."""

    detail = value if isinstance(value, Mapping) else {}
    identities: list[RebuildIdentity] = []
    for raw in detail.get("rebuild_identities") or ():
        if not isinstance(raw, Mapping):
            continue
        event_id = raw.get("event_id")
        revision = raw.get("revision")
        day_index = raw.get("day_index")
        source_hash = raw.get("source_hash")
        if (
            isinstance(event_id, str)
            and event_id.strip()
            and isinstance(revision, int)
            and not isinstance(revision, bool)
            and revision >= 1
            and isinstance(day_index, int)
            and not isinstance(day_index, bool)
            and day_index >= 0
            and isinstance(source_hash, str)
            and source_hash
        ):
            selected = raw.get("selected_option_index")
            identities.append(
                RebuildIdentity(
                    event_id=event_id,
                    revision=revision,
                    day_index=day_index,
                    source_hash=source_hash,
                    selected_option_index=(
                        selected
                        if isinstance(selected, int) and not isinstance(selected, bool)
                        else None
                    ),
                )
            )
    return tuple(sorted(identities, key=lambda item: item.day_index))
