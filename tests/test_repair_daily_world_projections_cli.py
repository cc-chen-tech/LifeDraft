"""Operator CLI safety contracts for world-projection repair."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime
from io import StringIO
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from scripts import repair_daily_world_projections as cli
from src.services import daily_world_projection_repair as repair
from src.database.models import (
    DailyWorldProjection,
    DailyWorldProjectionRepairAudit,
    Game,
    GameState,
)
from src.game.state import PlayerState
from src.game.state.player_data import default_world_projection_state
from src.services.daily_world_projection import DailyWorldProjectionService
from src.services.daily_world_projection_backup import (
    restore_state_backup,
    verify_state_backup,
)
from src.services.daily_world_projection_repair import (
    audit_rebuild_identities,
    non_projection_state_digest,
    scan_latest_game_states,
    verify_repair_invariants,
)


class WakeRecorder:
    def __init__(self) -> None:
        self.wake_count = 0

    def wake(self) -> None:
        self.wake_count += 1


class VisibleStateMutatingWake(WakeRecorder):
    def __init__(self, sessions, game_id: int) -> None:
        super().__init__()
        self.sessions = sessions
        self.game_id = game_id

    def wake(self) -> None:
        super().wake()
        if self.wake_count != 1:
            return
        with self.sessions() as session:
            latest = (
                session.query(GameState)
                .filter(GameState.game_id == self.game_id)
                .order_by(GameState.state_id.desc())
                .first()
            )
            changed = deepcopy(latest.state_json)
            changed["relationships"]["李长庚"] += 1
            session.add(
                GameState(
                    game_id=self.game_id,
                    week=latest.week,
                    age=latest.age,
                    state_json=changed,
                )
            )
            session.commit()


class CompletingProjectionWake(WakeRecorder):
    def __init__(self, sessions, game_id: int) -> None:
        super().__init__()
        self.sessions = sessions
        self.game_id = game_id

    def wake(self) -> None:
        super().wake()
        if self.wake_count != 1:
            return
        with self.sessions() as session:
            rows = session.query(DailyWorldProjection).filter(
                DailyWorldProjection.game_id == self.game_id
            )
            for row in rows:
                row.status = "ready_no_change"
                row.story_patch_json = {}
                row.option_patches_json = {"0": {}, "1": {}}
            session.commit()
        DailyWorldProjectionService(session_factory=self.sessions).apply_ready_for_game(
            self.game_id
        )


class SecondGameFencingWake(WakeRecorder):
    def __init__(self, sessions, game_id: int) -> None:
        super().__init__()
        self.sessions = sessions
        self.game_id = game_id

    def wake(self) -> None:
        super().wake()
        if self.wake_count != 2:
            return
        with self.sessions() as session:
            row = (
                session.query(DailyWorldProjection)
                .filter(DailyWorldProjection.game_id == self.game_id)
                .order_by(DailyWorldProjection.day_index)
                .first()
            )
            row.status = "superseded"
            session.commit()


class LowerFailureLaterCompleteWake(WakeRecorder):
    def __init__(self, sessions, failed_game_id: int, complete_game_id: int) -> None:
        super().__init__()
        self.sessions = sessions
        self.failed_game_id = failed_game_id
        self.complete_game_id = complete_game_id

    def wake(self) -> None:
        super().wake()
        if self.wake_count != 2:
            return
        with self.sessions() as session:
            latest = (
                session.query(GameState)
                .filter(GameState.game_id == self.failed_game_id)
                .order_by(GameState.state_id.desc())
                .first()
            )
            changed = deepcopy(latest.state_json)
            changed["relationships"]["李长庚"] += 1
            session.add(
                GameState(
                    game_id=self.failed_game_id,
                    week=latest.week,
                    age=latest.age,
                    state_json=changed,
                )
            )
            rows = session.query(DailyWorldProjection).filter(
                DailyWorldProjection.game_id == self.complete_game_id
            )
            for row in rows:
                row.status = "ready_no_change"
                row.story_patch_json = {}
                row.option_patches_json = {"0": {}, "1": {}}
            session.commit()
        DailyWorldProjectionService(session_factory=self.sessions).apply_ready_for_game(
            self.complete_game_id
        )


def _candidate_state(label: str) -> dict[str, object]:
    state = PlayerState().to_dict()
    state.update(
        {
            "timeline_version": 2,
            "timeline": {
                "version": 2,
                "start_date": "2026-08-17",
                "day_index": 2,
                "current_date": "2026-08-19",
            },
            "relationships": {"李长庚": 42},
            "day_history": [
                {
                    "event_id": f"{label}-day-{day_index}",
                    "revision": 1,
                    "day_index": day_index,
                    "story_date": f"2026-08-{17 + day_index:02d}",
                    "event_description": f"{label} 在第 {day_index} 天继续调查。",
                    "options": [
                        {"text": "继续", "effects": {}},
                        {"text": "休息", "effects": {}},
                    ],
                    "choice_option_index": 0,
                    "postprocessing_status": "failed",
                }
                for day_index in range(2)
            ],
            "world_projection_state": default_world_projection_state(),
        }
    )
    return state


def _healthy_state() -> dict[str, object]:
    state = _candidate_state("healthy")
    state["day_history"] = []
    state["world_projection_state"]["applied_through_day_index"] = -1
    return state


def _seed_game(session, state: dict[str, object]) -> int:
    game = Game(initial_state=deepcopy(state))
    session.add(game)
    session.flush()
    session.add(
        GameState(
            game_id=game.game_id,
            week=int(state["week"]),
            age=int(state["age"]),
            state_json=deepcopy(state),
        )
    )
    session.commit()
    return int(game.game_id)


def _db_snapshot(sessions) -> dict[str, object]:
    with sessions() as session:
        return {
            "states": [
                (row.state_id, row.game_id, deepcopy(row.state_json))
                for row in session.query(GameState).order_by(GameState.state_id)
            ],
            "projections": session.query(DailyWorldProjection).count(),
            "audits": session.query(DailyWorldProjectionRepairAudit).count(),
        }


def test_cli_defaults_to_read_only_dry_run(db_engine, capsys) -> None:
    """Default invocation must not create a DB row, audit, or backup."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        game_id = _seed_game(session, _candidate_state("default"))
    before = _db_snapshot(sessions)

    exit_code = cli.run([], session_factory=sessions)

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["report_hash"]
    assert output["candidates"][0]["game_id"] == game_id
    assert output["candidates"][0]["state_id"] > 0
    assert output["candidates"][0]["non_projection_digest"]
    assert _db_snapshot(sessions) == before


def test_apply_requires_exact_report_hash_before_any_write(
    db_engine, tmp_path: Path, capsys
) -> None:
    """A stale operator report must fail before backup or audit creation."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("stale"))
    backup_dir = tmp_path / "backups"
    before = _db_snapshot(sessions)

    exit_code = cli.run(
        [
            "--apply",
            "--expected-report-hash",
            "wrong",
            "--backup-dir",
            str(backup_dir),
        ],
        session_factory=sessions,
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "dry-run report changed" in captured.err
    assert not backup_dir.exists()
    assert _db_snapshot(sessions) == before


def test_apply_rechecks_visible_digest_before_first_backup_write(
    db_engine, tmp_path: Path, capsys, monkeypatch
) -> None:
    """An in-place state change after scan must be fenced before filesystem writes."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("pre-backup-race"))
    report = scan_latest_game_states(sessions)
    backup_dir = tmp_path / "must-not-exist"

    def changed_after_scan(*_args, **_kwargs):
        with sessions() as session:
            latest = session.query(GameState).one()
            changed = deepcopy(latest.state_json)
            changed["relationships"]["李长庚"] += 1
            latest.state_json = changed
            session.commit()
        return report

    monkeypatch.setattr(cli, "scan_latest_game_states", changed_after_scan)

    exit_code = cli.run(
        [
            "--apply",
            "--expected-report-hash",
            report.hash,
            "--backup-dir",
            str(backup_dir),
        ],
        session_factory=sessions,
        projection_service=WakeRecorder(),
    )

    assert exit_code == 1
    assert "changed after exact dry-run scan" in capsys.readouterr().err
    assert not backup_dir.exists()
    with sessions() as session:
        assert session.query(DailyWorldProjectionRepairAudit).count() == 0
        assert session.query(DailyWorldProjection).count() == 0


def test_backup_and_backed_up_audit_hold_the_game_serialization_lock(
    temp_db_file, tmp_path: Path, monkeypatch
) -> None:
    """A player snapshot cannot land between the final check and durable backup."""

    engine, _database_path = temp_db_file
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        game_id = _seed_game(session, _candidate_state("backup-lock"))
    report = scan_latest_game_states(sessions)
    entered_backup = threading.Event()
    release_backup = threading.Event()
    writer_done = threading.Event()
    apply_result: list[int] = []
    thread_errors: list[BaseException] = []
    original_write = cli.write_state_backup

    def blocked_backup(*args, **kwargs):
        entered_backup.set()
        assert release_backup.wait(5)
        return original_write(*args, **kwargs)

    monkeypatch.setattr(cli, "write_state_backup", blocked_backup)

    def run_apply() -> None:
        try:
            apply_result.append(
                cli.run(
                    [
                        "--apply",
                        "--expected-report-hash",
                        report.hash,
                        "--backup-dir",
                        str(tmp_path),
                    ],
                    session_factory=sessions,
                    projection_service=WakeRecorder(),
                    stdout=StringIO(),
                    stderr=StringIO(),
                )
            )
        except BaseException as exc:  # pragma: no cover - surfaced below
            thread_errors.append(exc)

    def save_player_snapshot() -> None:
        try:
            with sessions() as session:
                latest = (
                    session.query(GameState)
                    .filter(GameState.game_id == game_id)
                    .order_by(GameState.state_id.desc())
                    .first()
                )
                changed = deepcopy(latest.state_json)
                changed["relationships"]["李长庚"] += 1
                session.add(
                    GameState(
                        game_id=game_id,
                        week=latest.week,
                        age=latest.age,
                        state_json=changed,
                    )
                )
                session.commit()
            writer_done.set()
        except BaseException as exc:  # pragma: no cover - surfaced below
            thread_errors.append(exc)

    apply_thread = threading.Thread(target=run_apply)
    apply_thread.start()
    assert entered_backup.wait(5)
    writer_thread = threading.Thread(target=save_player_snapshot)
    writer_thread.start()
    assert writer_done.wait(0.2) is False
    release_backup.set()
    apply_thread.join(5)
    writer_thread.join(5)

    assert not thread_errors
    assert apply_result and apply_result[0] in {0, 1}
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        backup_files = list(tmp_path.glob("*.json"))
        assert backup_files == [Path(audit.backup_path)]
        assert verify_state_backup(audit.backup_path, audit.backup_sha256)


def test_apply_backs_up_and_enqueues_only_reported_games(
    db_engine, tmp_path: Path, capsys
) -> None:
    """Apply must use the exact report and persist oldest-first source identities."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        first_game = _seed_game(session, _candidate_state("first"))
        second_game = _seed_game(session, _candidate_state("second"))
        healthy_game = _seed_game(session, _healthy_state())
    report = scan_latest_game_states(sessions)
    service = WakeRecorder()

    exit_code = cli.run(
        [
            "--apply",
            "--expected-report-hash",
            report.hash,
            "--backup-dir",
            str(tmp_path),
        ],
        session_factory=sessions,
        projection_service=service,
    )

    capsys.readouterr()
    assert exit_code == 0
    with sessions() as session:
        rows = session.query(DailyWorldProjection).order_by(
            DailyWorldProjection.projection_id
        )
        assert [(row.game_id, row.day_index) for row in rows] == [
            (first_game, 0),
            (first_game, 1),
            (second_game, 0),
            (second_game, 1),
        ]
        assert healthy_game not in {row.game_id for row in rows}
        audits = session.query(DailyWorldProjectionRepairAudit).order_by(
            DailyWorldProjectionRepairAudit.game_id
        )
        assert [audit.status for audit in audits] == ["queued", "queued"]
        for audit in audits:
            assert verify_state_backup(audit.backup_path, audit.backup_sha256)
            identities = audit.detail_json["rebuild_identities"]
            assert [identity["day_index"] for identity in identities] == [0, 1]
    assert service.wake_count == 2


def test_game_filter_is_part_of_exact_report_hash(
    db_engine, tmp_path: Path, capsys
) -> None:
    """A filtered apply cannot silently expand to another candidate game."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        first_game = _seed_game(session, _candidate_state("filter-first"))
        second_game = _seed_game(session, _candidate_state("filter-second"))
    report = scan_latest_game_states(sessions, game_id=second_game)

    exit_code = cli.run(
        [
            "--apply",
            "--game-id",
            str(second_game),
            "--expected-report-hash",
            report.hash,
            "--backup-dir",
            str(tmp_path),
        ],
        session_factory=sessions,
        projection_service=WakeRecorder(),
    )

    capsys.readouterr()
    assert exit_code == 0
    with sessions() as session:
        assert {row.game_id for row in session.query(DailyWorldProjection).all()} == {
            second_game
        }
        assert first_game != second_game


def test_apply_initializes_only_missing_projection_layer(
    db_engine, tmp_path: Path, capsys
) -> None:
    """Legacy invalid projection data gets defaults without changing visible state."""

    sessions = sessionmaker(bind=db_engine)
    state = _candidate_state("initialize")
    state["world_projection_state"] = {"version": 0, "corrupt": True}
    before_digest = non_projection_state_digest(state)
    with sessions() as session:
        game_id = _seed_game(session, state)
    report = scan_latest_game_states(sessions)

    exit_code = cli.run(
        [
            "--apply",
            "--expected-report-hash",
            report.hash,
            "--backup-dir",
            str(tmp_path),
        ],
        session_factory=sessions,
        projection_service=WakeRecorder(),
    )

    capsys.readouterr()
    assert exit_code == 0
    with sessions() as session:
        latest = (
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
            .state_json
        )
        assert session.query(GameState).count() == 2
        assert non_projection_state_digest(latest) == before_digest
        assert latest["world_projection_state"] == default_world_projection_state()


def test_verified_backup_audit_survives_enqueue_conflict(
    db_engine, tmp_path: Path, capsys
) -> None:
    """A post-backup source fence failure must retain a backed-up audit trail."""

    sessions = sessionmaker(bind=db_engine)
    state = _candidate_state("source-conflict")
    with sessions() as session:
        game_id = _seed_game(session, state)
        record = state["day_history"][0]
        session.add(
            DailyWorldProjection(
                game_id=game_id,
                event_id=record["event_id"],
                revision=record["revision"],
                day_index=record["day_index"],
                story_date=record["story_date"],
                source_hash="stale-source-hash",
                status="pending",
                next_attempt_at=datetime.utcnow(),
            )
        )
        session.commit()
    report = scan_latest_game_states(sessions)

    exit_code = cli.run(
        [
            "--apply",
            "--expected-report-hash",
            report.hash,
            "--backup-dir",
            str(tmp_path),
        ],
        session_factory=sessions,
        projection_service=WakeRecorder(),
    )

    assert exit_code == 1
    assert "source_hash_conflict" in capsys.readouterr().err
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        assert audit.status == "backed_up"
        assert verify_state_backup(audit.backup_path, audit.backup_sha256)
        assert session.query(GameState).count() == 1


def test_replaced_source_hash_is_fenced_not_pending(
    db_engine, tmp_path: Path, capsys
) -> None:
    """A replacement of an audited source must stop wait immediately."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("source-replaced"))
    report = scan_latest_game_states(sessions)
    assert (
        cli.run(
            [
                "--apply",
                "--expected-report-hash",
                report.hash,
                "--backup-dir",
                str(tmp_path),
            ],
            session_factory=sessions,
            projection_service=WakeRecorder(),
        )
        == 0
    )
    capsys.readouterr()
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        row = (
            session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.day_index)
            .first()
        )
        row.source_hash = "replacement-source-hash"
        session.commit()
        audit_id = int(audit.audit_id)

    verification = verify_repair_invariants(sessions, audit_id)

    assert verification.status == "fenced"
    assert verification.detail == "projection_source_replaced"


def test_audit_identity_parser_rejects_partial_and_duplicate_lists() -> None:
    """One malformed identity must invalidate the entire durable marker list."""

    valid = {
        "event_id": "strict-day-0",
        "revision": 1,
        "day_index": 0,
        "source_hash": "a" * 64,
        "selected_option_index": 0,
    }
    missing_option = {
        "event_id": "strict-day-1",
        "revision": 1,
        "day_index": 1,
        "source_hash": "b" * 64,
    }

    assert (
        audit_rebuild_identities({"rebuild_identities": [valid, missing_option]}) == ()
    )
    assert (
        audit_rebuild_identities({"rebuild_identities": [valid, deepcopy(valid)]}) == ()
    )


def test_restore_refuses_when_non_projection_state_changed(
    db_engine, tmp_path: Path, capsys
) -> None:
    """Restore must exit 3 with zero writes after newer visible activity."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        game_id = _seed_game(session, _candidate_state("restore-refuse"))
    report = scan_latest_game_states(sessions)
    assert (
        cli.run(
            [
                "--apply",
                "--expected-report-hash",
                report.hash,
                "--backup-dir",
                str(tmp_path),
            ],
            session_factory=sessions,
            projection_service=WakeRecorder(),
        )
        == 0
    )
    capsys.readouterr()
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        latest = (
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
        )
        changed = deepcopy(latest.state_json)
        changed["relationships"]["李长庚"] += 1
        session.add(
            GameState(
                game_id=game_id,
                week=latest.week,
                age=latest.age,
                state_json=changed,
            )
        )
        session.commit()
        audit_id = int(audit.audit_id)
    before = _db_snapshot(sessions)

    exit_code = cli.run(["--restore-audit-id", str(audit_id)], session_factory=sessions)

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "non-projection state changed" in captured.err
    assert _db_snapshot(sessions) == before


def test_wait_timeout_is_terminal_but_never_reports_complete(
    db_engine, tmp_path: Path, capsys
) -> None:
    """Pending rows at the deadline must leave a timed-out auditable repair."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("wait-timeout"))
    report = scan_latest_game_states(sessions)

    exit_code = cli.run(
        [
            "--apply",
            "--expected-report-hash",
            report.hash,
            "--backup-dir",
            str(tmp_path),
            "--wait",
            "--timeout-seconds",
            "0",
        ],
        session_factory=sessions,
        projection_service=WakeRecorder(),
    )

    captured = capsys.readouterr()
    assert exit_code == 4
    assert "verified restore command" in captured.err
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        assert audit.status == "timed_out"
        assert audit.completed_at is not None


def test_wait_checks_all_games_for_fences_before_timing_out(
    db_engine, tmp_path: Path, capsys
) -> None:
    """A later game's superseded row must not hide behind an earlier pending game."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("first-pending"))
        fenced_game = _seed_game(session, _candidate_state("second-fenced"))
    report = scan_latest_game_states(sessions)

    exit_code = cli.run(
        [
            "--apply",
            "--expected-report-hash",
            report.hash,
            "--backup-dir",
            str(tmp_path),
            "--wait",
            "--timeout-seconds",
            "0",
        ],
        session_factory=sessions,
        projection_service=SecondGameFencingWake(sessions, fenced_game),
    )

    assert exit_code == 4
    assert "verified restore command" in capsys.readouterr().err
    with sessions() as session:
        audits = session.query(DailyWorldProjectionRepairAudit).order_by(
            DailyWorldProjectionRepairAudit.game_id
        )
        assert [audit.status for audit in audits] == ["timed_out", "failed_fenced"]


def test_wait_terminalizes_later_complete_game_after_lower_id_failure(
    db_engine, tmp_path: Path, capsys
) -> None:
    """One failed game must not prevent later audits from completing in the pass."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        failed_game = _seed_game(session, _candidate_state("lower-failed"))
        complete_game = _seed_game(session, _candidate_state("later-complete"))
    report = scan_latest_game_states(sessions)

    exit_code = cli.run(
        [
            "--apply",
            "--expected-report-hash",
            report.hash,
            "--backup-dir",
            str(tmp_path),
            "--wait",
            "--timeout-seconds",
            "0",
        ],
        session_factory=sessions,
        projection_service=LowerFailureLaterCompleteWake(
            sessions, failed_game, complete_game
        ),
    )

    assert exit_code == 3
    assert "verified restore command" in capsys.readouterr().err
    with sessions() as session:
        audits = session.query(DailyWorldProjectionRepairAudit).order_by(
            DailyWorldProjectionRepairAudit.game_id
        )
        assert [audit.status for audit in audits] == [
            "failed_invariant",
            "complete",
        ]


def test_wait_invariant_failure_stops_without_automatic_restore(
    db_engine, tmp_path: Path, capsys
) -> None:
    """Newer player activity must be retained and require an explicit restore."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        game_id = _seed_game(session, _candidate_state("wait-invariant"))
    report = scan_latest_game_states(sessions)
    service = VisibleStateMutatingWake(sessions, game_id)

    exit_code = cli.run(
        [
            "--apply",
            "--expected-report-hash",
            report.hash,
            "--backup-dir",
            str(tmp_path),
            "--wait",
            "--timeout-seconds",
            "1",
        ],
        session_factory=sessions,
        projection_service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "verified restore command" in captured.err
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        latest = (
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
        )
        assert audit.status == "failed_invariant"
        assert latest.state_json["relationships"]["李长庚"] == 43
        assert session.query(GameState).count() == 2


def test_wait_completes_only_after_applied_rows_and_contiguous_watermarks(
    db_engine, tmp_path: Path, capsys
) -> None:
    """Successful wait requires durable rows, source ledger, and both watermarks."""

    sessions = sessionmaker(bind=db_engine)
    initial = _candidate_state("wait-complete")
    with sessions() as session:
        game_id = _seed_game(session, initial)
    report = scan_latest_game_states(sessions)
    service = CompletingProjectionWake(sessions, game_id)

    exit_code = cli.run(
        [
            "--apply",
            "--expected-report-hash",
            report.hash,
            "--backup-dir",
            str(tmp_path),
            "--wait",
            "--timeout-seconds",
            "1",
        ],
        session_factory=sessions,
        projection_service=service,
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "complete"
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        latest = (
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
            .state_json
        )
        assert audit.status == "complete"
        assert non_projection_state_digest(latest) == audit.non_projection_digest_before
        assert latest["day_history"] == initial["day_history"]
        assert latest["world_projection_state"]["applied_through_day_index"] == 1
        assert latest["world_projection_state"]["projected_through_day_index"] == 1
        assert {row.status for row in session.query(DailyWorldProjection).all()} == {
            "applied"
        }
    assert scan_latest_game_states(sessions).candidates == ()


def test_wait_never_commits_complete_from_a_stale_verification(
    temp_db_file, tmp_path: Path, capsys, monkeypatch
) -> None:
    """Completion holds the game lock from final verification through its CAS."""

    engine, _database_path = temp_db_file
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        game_id = _seed_game(session, _candidate_state("atomic-complete"))
    report = scan_latest_game_states(sessions)
    assert (
        cli.run(
            [
                "--apply",
                "--expected-report-hash",
                report.hash,
                "--backup-dir",
                str(tmp_path),
            ],
            session_factory=sessions,
            projection_service=WakeRecorder(),
        )
        == 0
    )
    capsys.readouterr()
    with sessions() as session:
        audit_id = int(session.query(DailyWorldProjectionRepairAudit).one().audit_id)
        for row in session.query(DailyWorldProjection).all():
            row.status = "ready_no_change"
            row.story_patch_json = {}
            row.option_patches_json = {"0": {}, "1": {}}
        session.commit()
    DailyWorldProjectionService(session_factory=sessions).apply_ready_for_game(game_id)
    assert verify_repair_invariants(sessions, audit_id).status == "complete"

    verified = threading.Event()
    release_completion = threading.Event()
    writer_done = threading.Event()
    thread_errors: list[BaseException] = []
    original_verify = repair._verify_repair_invariants_in_session

    def blocked_verify(db, audit):
        verification = original_verify(db, audit)
        if verification.status == "complete":
            verified.set()
            assert release_completion.wait(5)
        return verification

    monkeypatch.setattr(repair, "_verify_repair_invariants_in_session", blocked_verify)

    def finalize() -> None:
        try:
            repair.finalize_repair_audit(sessions, audit_id)
        except BaseException as exc:  # pragma: no cover - surfaced below
            thread_errors.append(exc)

    def save_player_snapshot() -> None:
        try:
            with sessions() as session:
                latest = (
                    session.query(GameState)
                    .filter(GameState.game_id == game_id)
                    .order_by(GameState.state_id.desc())
                    .first()
                )
                changed = deepcopy(latest.state_json)
                changed["relationships"]["李长庚"] += 1
                session.add(
                    GameState(
                        game_id=game_id,
                        week=latest.week,
                        age=latest.age,
                        state_json=changed,
                    )
                )
                session.commit()
            writer_done.set()
        except BaseException as exc:  # pragma: no cover - surfaced below
            thread_errors.append(exc)

    finalize_thread = threading.Thread(target=finalize)
    finalize_thread.start()
    assert verified.wait(5)
    writer_thread = threading.Thread(target=save_player_snapshot)
    writer_thread.start()
    assert writer_done.wait(0.2) is False
    release_completion.set()
    finalize_thread.join(5)
    writer_thread.join(5)

    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        assert not thread_errors
        assert writer_done.is_set()
        assert audit.status == "complete"


def test_terminal_status_update_does_not_overwrite_concurrent_restore(
    db_engine, tmp_path: Path, capsys
) -> None:
    """Terminal status writes must CAS queued state and preserve restored audits."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("terminal-cas"))
    report = scan_latest_game_states(sessions)
    assert (
        cli.run(
            [
                "--apply",
                "--expected-report-hash",
                report.hash,
                "--backup-dir",
                str(tmp_path),
            ],
            session_factory=sessions,
            projection_service=WakeRecorder(),
        )
        == 0
    )
    capsys.readouterr()
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        audit.status = "restored"
        session.commit()
        audit_id = int(audit.audit_id)

    cli._mark_audit_terminal(
        sessions,
        audit_id,
        status="timed_out",
        digest_after="d" * 64,
    )

    with sessions() as session:
        audit = session.get(DailyWorldProjectionRepairAudit, audit_id)
        assert audit.status == "restored"


def test_restore_rejects_malformed_audit_without_writes(
    db_engine, tmp_path: Path, capsys
) -> None:
    """Malformed durable repair identities must fence restore before mutation."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("malformed-restore"))
    report = scan_latest_game_states(sessions)
    assert (
        cli.run(
            [
                "--apply",
                "--expected-report-hash",
                report.hash,
                "--backup-dir",
                str(tmp_path),
            ],
            session_factory=sessions,
            projection_service=WakeRecorder(),
        )
        == 0
    )
    capsys.readouterr()
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        malformed = deepcopy(audit.detail_json)
        malformed["rebuild_identities"][0].pop("selected_option_index")
        audit.detail_json = malformed
        session.commit()
        audit_id = int(audit.audit_id)
        state_count_before = session.query(GameState).count()
        statuses_before = [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ]

    exit_code = cli.run(["--restore-audit-id", str(audit_id)], session_factory=sessions)

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "malformed" in captured.err
    with sessions() as session:
        audit = session.get(DailyWorldProjectionRepairAudit, audit_id)
        assert audit.status == "queued"
        assert session.query(GameState).count() == state_count_before
        assert [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ] == statuses_before


def test_restore_uses_current_visible_fields_and_backup_projection_only(
    db_engine, tmp_path: Path, capsys
) -> None:
    """A safe restore creates a new snapshot without rewinding visible state."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        game_id = _seed_game(session, _candidate_state("restore-safe"))
    report = scan_latest_game_states(sessions)
    assert (
        cli.run(
            [
                "--apply",
                "--expected-report-hash",
                report.hash,
                "--backup-dir",
                str(tmp_path),
            ],
            session_factory=sessions,
            projection_service=WakeRecorder(),
        )
        == 0
    )
    capsys.readouterr()
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        backup_state = restore_state_backup(audit.backup_path, audit.backup_sha256)
        latest = (
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
        )
        projected = deepcopy(latest.state_json)
        projected["world_projection_state"]["applied_through_day_index"] = 1
        projected["world_projection_state"]["projected_through_day_index"] = 1
        session.add(
            GameState(
                game_id=game_id,
                week=latest.week,
                age=latest.age,
                state_json=projected,
            )
        )
        session.commit()
        audit_id = int(audit.audit_id)
        visible_digest = non_projection_state_digest(projected)

    exit_code = cli.run(["--restore-audit-id", str(audit_id)], session_factory=sessions)

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output == {"audit_id": audit_id, "status": "restored"}
    with sessions() as session:
        audit = session.get(DailyWorldProjectionRepairAudit, audit_id)
        restored = (
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
            .state_json
        )
        assert audit.status == "restored"
        assert non_projection_state_digest(restored) == visible_digest
        assert (
            restored["world_projection_state"] == backup_state["world_projection_state"]
        )
        assert {row.status for row in session.query(DailyWorldProjection).all()} == {
            "superseded"
        }
