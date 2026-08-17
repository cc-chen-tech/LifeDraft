#!/usr/bin/env python3
"""Safely scan, enqueue, verify, and restore daily world projection repairs."""

from __future__ import annotations

import argparse
import json
import sys
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, TextIO

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database.models import (
    DailyWorldProjection,
    DailyWorldProjectionRepairAudit,
    Game,
    GameState,
    SessionLocal,
)
from src.services.daily_world_projection import get_daily_world_projection_service
from src.services.daily_world_projection_backup import (
    BackupChecksumMismatch,
    create_repair_audit,
    restore_state_backup,
    verify_state_backup,
    write_state_backup,
)
from src.services.daily_world_projection_repair import (
    GameRepairCandidate,
    RepairScanReport,
    audit_rebuild_identities,
    enqueue_rebuild,
    finalize_repair_audit,
    initialized_projection_state,
    non_projection_state_digest,
    rebuild_identities,
    scan_latest_game_states,
)
from src.services.daily_world_projection_repository import (
    DailyWorldProjectionRepository,
)


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REPORT_CHANGED = 2
EXIT_INVARIANT = 3
EXIT_INCOMPLETE = 4


class NonProjectionStateChanged(RuntimeError):
    """A restore or repair was fenced by newer visible/current state."""


class RepairStateChanged(RuntimeError):
    """The exact dry-run state was replaced before DB enqueue."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repair versioned daily world projections safely."
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--restore-audit-id", type=int)
    parser.add_argument("--expected-report-hash")
    parser.add_argument("--game-id", type=int)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    return parser


def run(
    argv: Optional[Sequence[str]] = None,
    *,
    session_factory: Callable[[], Any] = SessionLocal,
    projection_service: Optional[Any] = None,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run one operator action and return a stable process exit code."""

    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        args = _parser().parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code)

    if args.timeout_seconds < 0:
        print("timeout-seconds must be non-negative", file=stderr)
        return EXIT_REPORT_CHANGED
    if args.restore_audit_id is not None:
        if args.wait or args.expected_report_hash or args.game_id is not None:
            print("restore mode does not accept apply filters", file=stderr)
            return EXIT_REPORT_CHANGED
        return _run_restore(
            args.restore_audit_id,
            session_factory=session_factory,
            stdout=stdout,
            stderr=stderr,
        )
    if args.wait and not args.apply:
        print("--wait requires --apply", file=stderr)
        return EXIT_REPORT_CHANGED

    report = scan_latest_game_states(session_factory, game_id=args.game_id)
    if not args.apply:
        _print_json(_report_payload(report), stdout)
        return EXIT_OK
    if not args.expected_report_hash or args.expected_report_hash != report.hash:
        print(
            "dry-run report changed; run dry-run again and supply its exact report hash",
            file=stderr,
        )
        return EXIT_REPORT_CHANGED

    service = projection_service or get_daily_world_projection_service()
    audit_ids: list[int] = []
    try:
        for candidate in report.candidates:
            audit_id = _apply_candidate(
                candidate,
                report,
                session_factory=session_factory,
                backup_dir=args.backup_dir,
            )
            audit_ids.append(audit_id)
            service.wake()
    except (RepairStateChanged, ValueError) as exc:
        print(str(exc), file=stderr)
        return EXIT_ERROR
    except Exception as exc:
        print(f"repair apply failed: {exc}", file=stderr)
        return EXIT_ERROR

    if args.wait:
        wait_result = _wait_for_audits(
            audit_ids,
            session_factory=session_factory,
            projection_service=service,
            timeout_seconds=args.timeout_seconds,
            monotonic=monotonic,
            sleep=sleep,
            stderr=stderr,
        )
        if wait_result != EXIT_OK:
            return wait_result

    _print_json(
        {
            "report_hash": report.hash,
            "audit_ids": audit_ids,
            "status": "complete" if args.wait else "queued",
        },
        stdout,
    )
    return EXIT_OK


def _apply_candidate(
    candidate: GameRepairCandidate,
    report: RepairScanReport,
    *,
    session_factory: Callable[[], Any],
    backup_dir: Optional[Path],
) -> int:
    if candidate.state_id is None or candidate.non_projection_digest is None:
        raise ValueError("repair candidate is missing exact state identity")
    with session_factory() as db, db.begin():
        _lock_game(db, candidate.game_id)
        state_row = _exact_candidate_state(db, candidate)
        state = deepcopy(state_row.state_json)
        identities = rebuild_identities(candidate, state)
        backup = write_state_backup(
            backup_dir,
            game_id=candidate.game_id,
            state_id=candidate.state_id,
            state_json=state,
        )
        verify_state_backup(backup.path, backup.sha256)
        detail = {
            "reasons": [reason.to_dict() for reason in candidate.reasons],
            "rebuild_day_indexes": list(candidate.rebuild_day_indexes),
            "rebuild_identities": [identity.to_dict() for identity in identities],
        }
        audit = create_repair_audit(
            db,
            game_id=candidate.game_id,
            state_id=candidate.state_id,
            report_hash=report.hash,
            backup_path=str(backup.path),
            backup_sha256=backup.sha256,
            non_projection_digest_before=candidate.non_projection_digest,
            detail_json=detail,
        )
        audit_id = int(audit.audit_id)

    with session_factory() as db, db.begin():
        _lock_game(db, candidate.game_id)
        latest = _exact_candidate_state(db, candidate)
        latest_state = latest.state_json
        audit = db.get(DailyWorldProjectionRepairAudit, audit_id)
        if audit is None or audit.status != "backed_up":
            raise RuntimeError("repair audit is not backed up")
        rebuilt = enqueue_rebuild(
            candidate, DailyWorldProjectionRepository(db), latest_state
        )
        if tuple(item.projection_key for item in rebuilt) != tuple(
            item.projection_key for item in identities
        ):
            raise RuntimeError("repair rebuild identity changed")
        projection_state, initialized = initialized_projection_state(latest_state)
        if initialized:
            repaired_state = deepcopy(dict(latest_state))
            repaired_state["world_projection_state"] = projection_state
            db.add(
                GameState(
                    game_id=candidate.game_id,
                    week=latest.week,
                    age=latest.age,
                    state_json=repaired_state,
                )
            )
        audit.status = "queued"
        db.flush()
    return audit_id


def _wait_for_audits(
    audit_ids: Sequence[int],
    *,
    session_factory: Callable[[], Any],
    projection_service: Any,
    timeout_seconds: float,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
    stderr: TextIO,
) -> int:
    deadline = monotonic() + timeout_seconds
    remaining = set(audit_ids)
    saw_invariant_failure = False
    saw_incomplete = False
    while remaining:
        pending: list[tuple[int, str]] = []
        for audit_id in sorted(remaining):
            verification = finalize_repair_audit(session_factory, audit_id)
            if verification.status == "complete":
                remaining.remove(audit_id)
                continue
            if verification.status == "failed_invariant":
                changed = _mark_audit_terminal(
                    session_factory,
                    audit_id,
                    status="failed_invariant",
                    digest_after=verification.non_projection_digest_after,
                )
                if changed:
                    _print_restore_command(audit_id, stderr)
                saw_invariant_failure = True
                remaining.remove(audit_id)
                continue
            if verification.status == "fenced":
                changed = _mark_audit_terminal(
                    session_factory,
                    audit_id,
                    status="failed_fenced",
                    digest_after=verification.non_projection_digest_after,
                )
                if changed:
                    _print_restore_command(audit_id, stderr)
                    saw_incomplete = True
                remaining.remove(audit_id)
                continue
            if verification.status in {
                "failed_fenced",
                "timed_out",
                "restored",
                "concurrent_terminal",
            }:
                if verification.status in {"failed_fenced", "timed_out"}:
                    saw_incomplete = True
                remaining.remove(audit_id)
                continue
            pending.append((audit_id, verification.non_projection_digest_after))
        if not remaining:
            break
        if monotonic() >= deadline:
            for audit_id, digest_after in pending:
                changed = _mark_audit_terminal(
                    session_factory,
                    audit_id,
                    status="timed_out",
                    digest_after=digest_after,
                )
                if changed:
                    _print_restore_command(audit_id, stderr)
                    saw_incomplete = True
                remaining.remove(audit_id)
            break
        projection_service.wake()
        sleep(min(0.25, max(0.0, deadline - monotonic())))
    if saw_invariant_failure:
        return EXIT_INVARIANT
    if saw_incomplete:
        return EXIT_INCOMPLETE
    return EXIT_OK


def _run_restore(
    audit_id: int,
    *,
    session_factory: Callable[[], Any],
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    try:
        audit_record = _read_audit(session_factory, audit_id)
        if not audit_rebuild_identities(audit_record["detail_json"]):
            raise ValueError("malformed repair audit identities")
        backup_state = restore_state_backup(
            audit_record["backup_path"], audit_record["backup_sha256"]
        )
        if not isinstance(backup_state, Mapping):
            raise BackupChecksumMismatch("backup checksum mismatch")
        with session_factory() as db, db.begin():
            audit = db.get(DailyWorldProjectionRepairAudit, audit_id)
            if audit is None:
                raise ValueError("repair audit not found")
            _lock_game(db, int(audit.game_id))
            identities = audit_rebuild_identities(audit.detail_json)
            if not identities:
                raise ValueError("malformed repair audit identities")
            latest = _latest_state(db, int(audit.game_id))
            if latest is None or not isinstance(latest.state_json, Mapping):
                raise NonProjectionStateChanged("non-projection state changed")
            current_digest = non_projection_state_digest(latest.state_json)
            if current_digest != audit.non_projection_digest_before:
                raise NonProjectionStateChanged("non-projection state changed")
            restored = deepcopy(dict(latest.state_json))
            if "world_projection_state" in backup_state:
                restored["world_projection_state"] = deepcopy(
                    backup_state["world_projection_state"]
                )
            else:
                restored.pop("world_projection_state", None)
            db.add(
                GameState(
                    game_id=audit.game_id,
                    week=latest.week,
                    age=latest.age,
                    state_json=restored,
                )
            )
            for identity in identities:
                rows = (
                    db.query(DailyWorldProjection)
                    .filter(
                        DailyWorldProjection.game_id == audit.game_id,
                        DailyWorldProjection.event_id == identity.event_id,
                        DailyWorldProjection.revision == identity.revision,
                        DailyWorldProjection.day_index == identity.day_index,
                        DailyWorldProjection.source_hash == identity.source_hash,
                        DailyWorldProjection.status != "superseded",
                    )
                    .all()
                )
                for row in rows:
                    row.status = "superseded"
                    row.lease_owner = None
                    row.lease_expires_at = None
                    row.updated_at = datetime.utcnow()
            audit.status = "restored"
            audit.non_projection_digest_after = current_digest
            audit.completed_at = datetime.utcnow()
        _print_json({"audit_id": audit_id, "status": "restored"}, stdout)
        return EXIT_OK
    except NonProjectionStateChanged as exc:
        print(str(exc), file=stderr)
        return EXIT_INVARIANT
    except (BackupChecksumMismatch, OSError, ValueError) as exc:
        print(f"restore failed: {exc}", file=stderr)
        return EXIT_INVARIANT


def _read_audit(session_factory: Callable[[], Any], audit_id: int) -> dict[str, Any]:
    with session_factory() as db:
        audit = db.get(DailyWorldProjectionRepairAudit, audit_id)
        if audit is None:
            raise ValueError("repair audit not found")
        return {
            "backup_path": str(audit.backup_path),
            "backup_sha256": str(audit.backup_sha256),
            "detail_json": deepcopy(audit.detail_json),
        }


def _latest_state(db: Any, game_id: int) -> Optional[GameState]:
    return (
        db.query(GameState)
        .filter(GameState.game_id == game_id)
        .order_by(GameState.state_id.desc())
        .first()
    )


def _exact_candidate_state(db: Any, candidate: GameRepairCandidate) -> GameState:
    latest = _latest_state(db, candidate.game_id)
    if (
        latest is None
        or candidate.state_id is None
        or int(latest.state_id) != candidate.state_id
        or not isinstance(latest.state_json, Mapping)
        or candidate.non_projection_digest is None
        or non_projection_state_digest(latest.state_json)
        != candidate.non_projection_digest
    ):
        raise RepairStateChanged(
            f"game {candidate.game_id} changed after exact dry-run scan"
        )
    return latest


def _lock_game(db: Any, game_id: int) -> None:
    if db.get_bind().dialect.name == "sqlite":
        result = db.execute(
            text(
                "UPDATE games SET updated_at = updated_at " "WHERE game_id = :game_id"
            ),
            {"game_id": game_id},
        )
        if result.rowcount != 1:
            raise ValueError("game not found")
        return
    if (
        db.query(Game).filter(Game.game_id == game_id).with_for_update().one_or_none()
        is None
    ):
        raise ValueError("game not found")


def _mark_audit_terminal(
    session_factory: Callable[[], Any],
    audit_id: int,
    *,
    status: str,
    digest_after: str,
) -> bool:
    with session_factory() as db, db.begin():
        exists = db.get(DailyWorldProjectionRepairAudit, audit_id)
        if exists is None:
            raise ValueError("repair audit not found")
        updated = (
            db.query(DailyWorldProjectionRepairAudit)
            .filter(
                DailyWorldProjectionRepairAudit.audit_id == audit_id,
                DailyWorldProjectionRepairAudit.status == "queued",
            )
            .update(
                {
                    DailyWorldProjectionRepairAudit.status: status,
                    DailyWorldProjectionRepairAudit.non_projection_digest_after: (
                        digest_after or None
                    ),
                    DailyWorldProjectionRepairAudit.completed_at: datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        return updated == 1


def _report_payload(report: RepairScanReport) -> dict[str, Any]:
    return {"report_hash": report.hash, **report.to_dict()}


def _print_restore_command(audit_id: int, stream: TextIO) -> None:
    print(
        "verified restore command: "
        f"python scripts/repair_daily_world_projections.py --restore-audit-id {audit_id}",
        file=stream,
    )


def _print_json(value: Mapping[str, Any], stream: TextIO) -> None:
    print(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=stream,
    )


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
