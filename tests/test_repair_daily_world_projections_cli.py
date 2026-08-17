"""Operator CLI safety contracts for world-projection repair."""

from __future__ import annotations

import json
import hashlib
import shlex
import threading
from copy import deepcopy
from datetime import datetime
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

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
from src.game.world_projection_schema import compute_projection_source_hash
from src.api.session_store import session_store
from src.services.daily_world_projection import DailyWorldProjectionService
from src.services.daily_world_projection_backup import (
    restore_state_backup,
    verify_state_backup,
    write_state_backup,
)
from src.services.daily_world_projection_repair import (
    audit_rebuild_identities,
    non_projection_state_digest,
    rebuild_identities,
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


class RestoreOnSecondWake(WakeRecorder):
    def __init__(self, sessions) -> None:
        super().__init__()
        self.sessions = sessions

    def wake(self) -> None:
        super().wake()
        if self.wake_count != 2:
            return
        with self.sessions() as session:
            audit = session.query(DailyWorldProjectionRepairAudit).one()
            audit.status = "complete"
            audit_id = int(audit.audit_id)
            report_hash = str(audit.report_hash)
            session.commit()
        assert (
            cli.run(
                [
                    "--restore-audit-id",
                    str(audit_id),
                    "--expected-report-hash",
                    report_hash,
                    "--confirm-writers-stopped",
                ],
                session_factory=self.sessions,
                stdout=StringIO(),
                stderr=StringIO(),
            )
            == 0
        )


def test_restore_requires_explicit_offline_confirmation(temp_db_file) -> None:
    sessions = sessionmaker(bind=temp_db_file, expire_on_commit=False)
    stderr = StringIO()

    result = cli.run(
        ["--restore-audit-id", "1", "--expected-report-hash", "deadbeef"],
        session_factory=sessions,
        stdout=StringIO(),
        stderr=stderr,
    )

    assert result == cli.EXIT_REPORT_CHANGED
    assert "--confirm-writers-stopped" in stderr.getvalue()


def test_restore_rejects_cross_game_wrong_state_and_format_before_writes(
    db_engine, tmp_path: Path
) -> None:
    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("backup-owner"))
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
            stdout=StringIO(),
            stderr=StringIO(),
        )
        == cli.EXIT_OK
    )
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        audit.status = "complete"
        audit_id = int(audit.audit_id)
        game_id = int(audit.game_id)
        state_id = int(audit.state_id)
        original_state = restore_state_backup(
            audit.backup_path,
            audit.backup_sha256,
            expected_game_id=game_id,
            expected_state_id=state_id,
        )
        session.commit()

    cross_game = write_state_backup(
        tmp_path / "cross-game",
        game_id=game_id + 1000,
        state_id=state_id,
        state_json=original_state,
    )
    wrong_state = write_state_backup(
        tmp_path / "wrong-state",
        game_id=game_id,
        state_id=state_id + 1000,
        state_json=original_state,
    )
    bad_format = write_state_backup(
        tmp_path / "bad-format",
        game_id=game_id,
        state_id=state_id,
        state_json=original_state,
    )
    payload = json.loads(bad_format.path.read_text(encoding="utf-8"))
    payload["metadata"]["backup_format_version"] = 0
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    bad_format.path.write_bytes(encoded)
    cases = [
        (cross_game.path, cross_game.sha256),
        (wrong_state.path, wrong_state.sha256),
        (bad_format.path, hashlib.sha256(encoded).hexdigest()),
    ]

    for backup_path, backup_sha256 in cases:
        with sessions() as session:
            audit = session.get(DailyWorldProjectionRepairAudit, audit_id)
            audit.backup_path = str(backup_path)
            audit.backup_sha256 = backup_sha256
            session.commit()
        before = _db_snapshot(sessions)
        assert (
            cli.run(
                [
                    "--restore-audit-id",
                    str(audit_id),
                    "--expected-report-hash",
                    report.hash,
                    "--confirm-writers-stopped",
                ],
                session_factory=sessions,
                stdout=StringIO(),
                stderr=StringIO(),
            )
            == cli.EXIT_INVARIANT
        )
        assert _db_snapshot(sessions) == before


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


def test_weekly_v1_dry_run_has_zero_candidates_and_zero_writes(
    db_engine, capsys
) -> None:
    sessions = sessionmaker(bind=db_engine)
    weekly = _candidate_state("weekly-v1")
    weekly.pop("timeline")
    weekly["timeline_version"] = 1
    with sessions() as session:
        _seed_game(session, weekly)
    before = _db_snapshot(sessions)

    assert cli.run(["--dry-run"], session_factory=sessions) == cli.EXIT_OK

    output = json.loads(capsys.readouterr().out)
    assert output["candidates"] == []
    assert _db_snapshot(sessions) == before


def test_legacy_unproven_watermark_is_reset_and_rebuilt_from_day_zero(
    db_engine, tmp_path: Path, capsys
) -> None:
    sessions = sessionmaker(bind=db_engine)
    state = _candidate_state("legacy-baseline")
    state["world_projection_state"] = default_world_projection_state()
    state["world_projection_state"].update(
        {
            "applied_through_day_index": 1,
            "projected_through_day_index": 1,
            "applied_sources": [],
            "world": {
                **state["world_projection_state"]["world"],
                "fact_updates": [{"fact": "unprovable legacy derived fact"}],
            },
        }
    )
    before_digest = non_projection_state_digest(state)
    with sessions() as session:
        game_id = _seed_game(session, state)
    report = scan_latest_game_states(sessions)

    assert report.candidates[0].rebuild_day_indexes == [0, 1]
    assert (
        cli.run(
            [
                "--apply",
                "--expected-report-hash",
                report.hash,
                "--backup-dir",
                str(tmp_path),
                "--wait",
            ],
            session_factory=sessions,
            projection_service=CompletingProjectionWake(sessions, game_id),
        )
        == cli.EXIT_OK
    )
    capsys.readouterr()

    with sessions() as session:
        rows = (
            session.query(DailyWorldProjection)
            .filter(DailyWorldProjection.game_id == game_id)
            .order_by(DailyWorldProjection.day_index)
            .all()
        )
        latest = (
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
            .state_json
        )
        audit = session.query(DailyWorldProjectionRepairAudit).one()

    assert [row.status for row in rows] == ["applied", "applied"]
    assert audit.status == "complete"
    assert non_projection_state_digest(latest) == before_digest
    layer = latest["world_projection_state"]
    expected_layer = default_world_projection_state()
    expected_layer["applied_through_day_index"] = 1
    expected_layer["projected_through_day_index"] = 1
    expected_layer["applied_sources"] = [
        {
            "event_id": record["event_id"],
            "revision": record["revision"],
            "day_index": record["day_index"],
            "source_hash": compute_projection_source_hash(
                record["event_description"], record["options"]
            ),
            "option_index": record["choice_option_index"],
        }
        for record in state["day_history"]
    ]
    assert layer == expected_layer


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
    assert json.loads(captured.out) == {
        "audit_ids": [],
        "report_hash": scan_latest_game_states(sessions).hash,
        "status": "report_changed",
    }
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
        assert verify_state_backup(
            audit.backup_path,
            audit.backup_sha256,
            expected_game_id=audit.game_id,
            expected_state_id=audit.state_id,
        )


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
            assert verify_state_backup(
                audit.backup_path,
                audit.backup_sha256,
                expected_game_id=audit.game_id,
                expected_state_id=audit.state_id,
            )
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
        assert verify_state_backup(
            audit.backup_path,
            audit.backup_sha256,
            expected_game_id=audit.game_id,
            expected_state_id=audit.state_id,
        )
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
    second = {**missing_option, "selected_option_index": 0}
    invalid_hash = {**valid, "source_hash": "not-a-sha256"}

    assert (
        audit_rebuild_identities(
            {
                "rebuild_day_indexes": [0, 1],
                "rebuild_identities": [valid, missing_option],
            }
        )
        == ()
    )
    assert (
        audit_rebuild_identities(
            {
                "rebuild_day_indexes": [0],
                "rebuild_identities": [invalid_hash],
            }
        )
        == ()
    )
    assert (
        audit_rebuild_identities(
            {
                "rebuild_day_indexes": [0],
                "rebuild_identities": [valid, deepcopy(valid)],
            }
        )
        == ()
    )
    assert (
        audit_rebuild_identities(
            {
                "rebuild_day_indexes": [0, 1],
                "rebuild_identities": [valid],
            }
        )
        == ()
    )
    assert [
        identity.day_index
        for identity in audit_rebuild_identities(
            {
                "rebuild_day_indexes": [0, 1],
                "rebuild_identities": [valid, second],
            }
        )
    ] == [0, 1]


def test_restore_rejects_truncated_two_day_audit_without_writes(
    db_engine, tmp_path: Path, capsys
) -> None:
    """Removing one durable identity cannot authorize a partial restore."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("truncated-restore"))
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
        detail = deepcopy(audit.detail_json)
        assert detail["rebuild_day_indexes"] == [0, 1]
        detail["rebuild_identities"] = detail["rebuild_identities"][:1]
        audit.detail_json = detail
        audit.status = "complete"
        session.commit()
        audit_id = int(audit.audit_id)
        state_count_before = session.query(GameState).count()
        projection_statuses_before = [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ]

    exit_code = cli.run(
        [
            "--restore-audit-id",
            str(audit_id),
            "--expected-report-hash",
            report.hash,
            "--confirm-writers-stopped",
        ],
        session_factory=sessions,
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "malformed" in captured.err
    with sessions() as session:
        audit = session.get(DailyWorldProjectionRepairAudit, audit_id)
        assert audit.status == "complete"
        assert session.query(GameState).count() == state_count_before
        assert [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ] == projection_statuses_before


def test_verify_and_restore_reject_both_lists_truncated_from_verified_backup(
    db_engine, tmp_path: Path, capsys
) -> None:
    """The verified original backup, not two mutable audit lists, fixes scope."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        game_id = _seed_game(session, _candidate_state("both-lists-truncated"))
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
        day_zero = (
            session.query(DailyWorldProjection)
            .filter(
                DailyWorldProjection.game_id == game_id,
                DailyWorldProjection.day_index == 0,
            )
            .one()
        )
        day_zero.status = "ready_no_change"
        day_zero.story_patch_json = {}
        day_zero.option_patches_json = {"0": {}, "1": {}}
        session.commit()
    assert (
        DailyWorldProjectionService(session_factory=sessions).apply_ready_for_game(
            game_id
        )
        == 1
    )

    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        detail = deepcopy(audit.detail_json)
        detail["rebuild_day_indexes"] = [0]
        detail["rebuild_identities"] = detail["rebuild_identities"][:1]
        audit.detail_json = detail
        audit.status = "complete"
        session.commit()
        audit_id = int(audit.audit_id)
        state_count_before = session.query(GameState).count()
        projection_statuses_before = [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ]

    verification = verify_repair_invariants(sessions, audit_id)
    restore_exit = cli.run(
        [
            "--restore-audit-id",
            str(audit_id),
            "--expected-report-hash",
            report.hash,
            "--confirm-writers-stopped",
        ],
        session_factory=sessions,
    )

    captured = capsys.readouterr()
    assert verification.status == "failed_invariant"
    assert restore_exit == 3
    assert "scope" in captured.err
    with sessions() as session:
        audit = session.get(DailyWorldProjectionRepairAudit, audit_id)
        assert audit.status == "complete"
        assert session.query(GameState).count() == state_count_before
        assert [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ] == projection_statuses_before


def test_restore_rechecks_audit_scope_after_game_lock(
    db_engine, tmp_path: Path, capsys, monkeypatch
) -> None:
    """A scope change while waiting for the game lock must fence restore."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("restore-scope-lock"))
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
        audit.status = "complete"
        session.commit()
        audit_id = int(audit.audit_id)
        state_count_before = session.query(GameState).count()
        projection_statuses_before = [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ]

    original_lock_game = cli._lock_game
    scope_changed = False

    def change_scope_then_lock(db, game_id):
        nonlocal scope_changed
        if not scope_changed:
            with sessions() as other:
                audit = other.get(DailyWorldProjectionRepairAudit, audit_id)
                detail = deepcopy(audit.detail_json)
                detail["rebuild_day_indexes"] = [0]
                detail["rebuild_identities"] = detail["rebuild_identities"][:1]
                audit.detail_json = detail
                other.commit()
            scope_changed = True
        return original_lock_game(db, game_id)

    monkeypatch.setattr(cli, "_lock_game", change_scope_then_lock)

    exit_code = cli.run(
        [
            "--restore-audit-id",
            str(audit_id),
            "--expected-report-hash",
            report.hash,
            "--confirm-writers-stopped",
        ],
        session_factory=sessions,
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "scope binding changed" in captured.err
    with sessions() as session:
        audit = session.get(DailyWorldProjectionRepairAudit, audit_id)
        assert audit.status == "complete"
        assert audit.detail_json["rebuild_day_indexes"] == [0]
        assert session.query(GameState).count() == state_count_before
        assert [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ] == projection_statuses_before


def test_future_ledger_is_reset_so_rebuild_materializes_day_zero_patch(
    db_engine, tmp_path: Path, capsys
) -> None:
    """A source ahead of watermark cannot suppress its real rebuild patch."""

    sessions = sessionmaker(bind=db_engine)
    state = _candidate_state("future-ledger")
    day_zero = state["day_history"][0]
    state["world_projection_state"]["applied_sources"] = [
        {
            "event_id": day_zero["event_id"],
            "revision": day_zero["revision"],
            "day_index": 0,
            "source_hash": compute_projection_source_hash(
                day_zero["event_description"], day_zero["options"]
            ),
            "option_index": day_zero["choice_option_index"],
        }
    ]
    with sessions() as session:
        game_id = _seed_game(session, state)
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
        latest = (
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
        )
        assert latest.state_json["world_projection_state"]["applied_sources"] == []
        row = (
            session.query(DailyWorldProjection)
            .filter(
                DailyWorldProjection.game_id == game_id,
                DailyWorldProjection.day_index == 0,
            )
            .one()
        )
        row.status = "ready"
        row.story_patch_json = {
            "fact_updates": [
                {
                    "action": "new",
                    "subject": "day-zero",
                    "category": "situation",
                    "fact": "future ledger did not suppress this patch",
                }
            ]
        }
        row.option_patches_json = {"0": {}, "1": {}}
        session.commit()

    assert (
        DailyWorldProjectionService(session_factory=sessions).apply_ready_for_game(
            game_id
        )
        == 1
    )
    with sessions() as session:
        latest = (
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
            .state_json
        )
        facts = latest["world_projection_state"]["world"]["fact_updates"]
        assert [fact["fact"] for fact in facts] == [
            "future ledger did not suppress this patch"
        ]


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
        audit.status = "complete"
        session.commit()
    before = _db_snapshot(sessions)

    exit_code = cli.run(
        [
            "--restore-audit-id",
            str(audit_id),
            "--expected-report-hash",
            report.hash,
            "--confirm-writers-stopped",
        ],
        session_factory=sessions,
    )

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


def test_wait_restore_on_wake_never_reports_complete(
    db_engine, tmp_path: Path, capsys
) -> None:
    """A concurrently restored audit is non-complete even when no work remains."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("restore-on-wake"))
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
            "1",
        ],
        session_factory=sessions,
        projection_service=RestoreOnSecondWake(sessions),
    )

    captured = capsys.readouterr()
    assert exit_code == 4
    assert '"status":"complete"' not in captured.out
    with sessions() as session:
        assert session.query(DailyWorldProjectionRepairAudit).one().status == "restored"


def test_wait_cas_miss_maps_durable_restored_status_to_incomplete(
    db_engine, tmp_path: Path, capsys, monkeypatch
) -> None:
    """A failed terminal CAS must map the durable winner, never assume success."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        game_id = _seed_game(session, _candidate_state("cas-miss-restored"))
    report = scan_latest_game_states(sessions)
    original_mark = cli._mark_audit_terminal

    def restore_before_mark(session_factory, audit_id, *, status, digest_after):
        with sessions() as session:
            audit = session.get(DailyWorldProjectionRepairAudit, audit_id)
            audit.status = "restored"
            session.commit()
        return original_mark(
            session_factory,
            audit_id,
            status=status,
            digest_after=digest_after,
        )

    monkeypatch.setattr(cli, "_mark_audit_terminal", restore_before_mark)

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
        projection_service=SecondGameFencingWake(sessions, game_id),
    )

    captured = capsys.readouterr()
    assert exit_code == 4
    assert '"status":"complete"' not in captured.out
    with sessions() as session:
        assert session.query(DailyWorldProjectionRepairAudit).one().status == "restored"


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

    def blocked_verify(db, audit, identities):
        verification = original_verify(db, audit, identities)
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
        audit.status = "complete"
        session.commit()
        audit_id = int(audit.audit_id)
        state_count_before = session.query(GameState).count()
        statuses_before = [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ]

    exit_code = cli.run(
        [
            "--restore-audit-id",
            str(audit_id),
            "--expected-report-hash",
            report.hash,
            "--confirm-writers-stopped",
        ],
        session_factory=sessions,
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "malformed" in captured.err
    with sessions() as session:
        audit = session.get(DailyWorldProjectionRepairAudit, audit_id)
        assert audit.status == "complete"
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
        backup_state = restore_state_backup(
            audit.backup_path,
            audit.backup_sha256,
            expected_game_id=audit.game_id,
            expected_state_id=audit.state_id,
        )
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
        audit.status = "complete"
        session.commit()
        visible_digest = non_projection_state_digest(projected)

    session_store.remove_game_sessions(game_id)
    session_store.put(
        game_id,
        SimpleNamespace(player_state=PlayerState.from_dict(projected)),
        user_id=991,
    )
    assert session_store.get_game_sessions(game_id)

    exit_code = cli.run(
        [
            "--restore-audit-id",
            str(audit_id),
            "--expected-report-hash",
            report.hash,
            "--confirm-writers-stopped",
        ],
        session_factory=sessions,
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output == {"audit_id": audit_id, "status": "restored"}
    assert session_store.get_game_sessions(game_id) == []
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


def test_wait_failure_prints_one_machine_readable_scope_payload(
    db_engine, tmp_path: Path
) -> None:
    """A nonzero wait still preserves the exact report/audit evidence on stdout."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("failure-payload"))
    report = scan_latest_game_states(sessions)
    stdout = StringIO()
    stderr = StringIO()

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
        stdout=stdout,
        stderr=stderr,
    )

    payloads = [json.loads(line) for line in stdout.getvalue().splitlines() if line]
    assert exit_code == cli.EXIT_INCOMPLETE
    assert payloads == [
        {
            "audit_ids": [1],
            "report_hash": report.hash,
            "status": "timed_out",
        }
    ]
    assert "verified restore command" in stderr.getvalue()


def test_partial_apply_exception_prints_the_durable_partial_scope(
    db_engine, tmp_path: Path, monkeypatch
) -> None:
    """A later candidate failure cannot erase evidence for earlier audit rows."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("partial-first"))
        _seed_game(session, _candidate_state("partial-second"))
    report = scan_latest_game_states(sessions)
    original_apply = cli._apply_candidate
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected partial apply failure")
        return original_apply(*args, **kwargs)

    monkeypatch.setattr(cli, "_apply_candidate", fail_second)
    stdout = StringIO()

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
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == cli.EXIT_ERROR
    assert [json.loads(line) for line in stdout.getvalue().splitlines() if line] == [
        {"audit_ids": [1], "report_hash": report.hash, "status": "apply_failed"}
    ]


def test_source_hash_conflict_preserves_every_durable_audit_id_in_partial_output(
    db_engine, tmp_path: Path
) -> None:
    """A second-stage conflict cannot hide either queued or backed-up audits."""

    sessions = sessionmaker(bind=db_engine)
    first_state = _candidate_state("durable-first")
    conflicting_state = _candidate_state("durable-conflict")
    with sessions() as session:
        _seed_game(session, first_state)
        conflicting_game_id = _seed_game(session, conflicting_state)
    report = scan_latest_game_states(sessions)
    conflicting_candidate = next(
        candidate
        for candidate in report.candidates
        if candidate.game_id == conflicting_game_id
    )
    conflicting_identity = rebuild_identities(conflicting_candidate, conflicting_state)[
        0
    ]
    with sessions() as session:
        session.add(
            DailyWorldProjection(
                game_id=conflicting_game_id,
                event_id=conflicting_identity.event_id,
                revision=conflicting_identity.revision,
                day_index=conflicting_identity.day_index,
                source_hash="f" * 64,
                status="pending",
                next_attempt_at=datetime.utcnow(),
            )
        )
        session.commit()

    stdout = StringIO()
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
        stdout=stdout,
        stderr=StringIO(),
    )

    payload = json.loads(stdout.getvalue())
    with sessions() as session:
        durable = [
            (int(audit.audit_id), audit.status)
            for audit in session.query(DailyWorldProjectionRepairAudit)
            .order_by(DailyWorldProjectionRepairAudit.audit_id)
            .all()
        ]
    assert exit_code == cli.EXIT_ERROR
    assert durable == [(1, "queued"), (2, "backed_up")]
    assert payload == {
        "audit_ids": [audit_id for audit_id, _status in durable],
        "report_hash": report.hash,
        "status": "apply_failed",
    }


def test_timeout_restore_command_is_a_guarded_executable_terminal_intent(
    db_engine, tmp_path: Path
) -> None:
    """The terminal timeout command remains an explicit, safe restore intent."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("timeout-restore-command"))
    report = scan_latest_game_states(sessions)
    stderr = StringIO()

    assert (
        cli.run(
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
            stdout=StringIO(),
            stderr=stderr,
        )
        == cli.EXIT_INCOMPLETE
    )
    command = next(
        line.removeprefix("verified restore command: ")
        for line in stderr.getvalue().splitlines()
        if line.startswith("verified restore command: ")
    )

    assert (
        cli.run(
            shlex.split(command)[2:],
            session_factory=sessions,
            stdout=StringIO(),
            stderr=StringIO(),
        )
        == cli.EXIT_OK
    )
    with sessions() as session:
        assert session.query(DailyWorldProjectionRepairAudit).one().status == "restored"


def test_failed_invariant_restore_command_refuses_changed_visible_state(
    db_engine, tmp_path: Path
) -> None:
    """An explicit terminal restore still cannot overwrite player activity."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        game_id = _seed_game(session, _candidate_state("failed-invariant-restore"))
    report = scan_latest_game_states(sessions)
    stderr = StringIO()
    assert (
        cli.run(
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
            projection_service=VisibleStateMutatingWake(sessions, game_id),
            stdout=StringIO(),
            stderr=stderr,
        )
        == cli.EXIT_INVARIANT
    )
    command = next(
        line.removeprefix("verified restore command: ")
        for line in stderr.getvalue().splitlines()
        if line.startswith("verified restore command: ")
    )
    before = _db_snapshot(sessions)

    assert (
        cli.run(
            shlex.split(command)[2:],
            session_factory=sessions,
            stdout=StringIO(),
            stderr=StringIO(),
        )
        == cli.EXIT_INVARIANT
    )
    assert _db_snapshot(sessions) == before


def test_restore_requires_the_exact_expected_report_hash_before_any_write(
    db_engine, tmp_path: Path
) -> None:
    """Restore is never an ID-only operation, even for a valid completed audit."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        _seed_game(session, _candidate_state("restore-expected-hash"))
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
            stdout=StringIO(),
            stderr=StringIO(),
        )
        == 0
    )
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        audit.status = "complete"
        audit_id = int(audit.audit_id)
        before = _db_snapshot(sessions)

    missing = cli.run(
        ["--restore-audit-id", str(audit_id)],
        session_factory=sessions,
        stdout=StringIO(),
        stderr=StringIO(),
    )
    wrong = cli.run(
        [
            "--restore-audit-id",
            str(audit_id),
            "--expected-report-hash",
            "wrong",
            "--confirm-writers-stopped",
        ],
        session_factory=sessions,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert missing == cli.EXIT_REPORT_CHANGED
    assert wrong != cli.EXIT_OK
    assert _db_snapshot(sessions) == before


def _clone_audit(
    audit: DailyWorldProjectionRepairAudit, *, audit_id: int, game_id: int
) -> DailyWorldProjectionRepairAudit:
    return DailyWorldProjectionRepairAudit(
        audit_id=audit_id,
        game_id=game_id,
        state_id=audit.state_id,
        report_hash=audit.report_hash,
        backup_path=audit.backup_path,
        backup_sha256=audit.backup_sha256,
        non_projection_digest_before=audit.non_projection_digest_before,
        non_projection_digest_after=audit.non_projection_digest_after,
        status="complete",
        detail_json=deepcopy(audit.detail_json),
        completed_at=datetime.utcnow(),
    )


def _two_completed_restore_audits(sessions, tmp_path: Path) -> tuple[int, int, str]:
    with sessions() as session:
        first_game = _seed_game(session, _candidate_state("restore-audit-a"))
        second_game = _seed_game(session, _candidate_state("restore-audit-b"))
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
            stdout=StringIO(),
            stderr=StringIO(),
        )
        == cli.EXIT_OK
    )
    with sessions() as session:
        audits = (
            session.query(DailyWorldProjectionRepairAudit)
            .order_by(DailyWorldProjectionRepairAudit.game_id)
            .all()
        )
        first, second = audits
        first.audit_id = 100
        second.audit_id = 102
        first.status = "complete"
        second.status = "complete"
        session.commit()
    return first_game, second_game, report.hash


def test_restore_rejects_interleaved_newer_audit_for_the_selected_game(
    db_engine, tmp_path: Path
) -> None:
    """A same-game audit between two scope IDs fences the older restore."""

    sessions = sessionmaker(bind=db_engine)
    first_game, _second_game, report_hash = _two_completed_restore_audits(
        sessions, tmp_path
    )
    with sessions() as session:
        first = session.get(DailyWorldProjectionRepairAudit, 100)
        session.add(_clone_audit(first, audit_id=101, game_id=first_game))
        session.commit()
        state_count_before = session.query(GameState).count()
        projection_statuses_before = [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ]

    exit_code = cli.run(
        [
            "--restore-audit-id",
            "100",
            "--expected-report-hash",
            report_hash,
            "--confirm-writers-stopped",
        ],
        session_factory=sessions,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == cli.EXIT_INVARIANT
    with sessions() as session:
        assert session.query(GameState).count() == state_count_before
        assert session.get(DailyWorldProjectionRepairAudit, 100).status == "complete"
        assert [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ] == projection_statuses_before


def test_restore_allows_interleaved_audit_for_a_different_game(
    db_engine, tmp_path: Path
) -> None:
    """An unrelated game's later audit must not block the selected game restore."""

    sessions = sessionmaker(bind=db_engine)
    _first_game, second_game, report_hash = _two_completed_restore_audits(
        sessions, tmp_path
    )
    with sessions() as session:
        second = session.get(DailyWorldProjectionRepairAudit, 102)
        session.add(_clone_audit(second, audit_id=101, game_id=second_game))
        session.commit()

    exit_code = cli.run(
        [
            "--restore-audit-id",
            "100",
            "--expected-report-hash",
            report_hash,
            "--confirm-writers-stopped",
        ],
        session_factory=sessions,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == cli.EXIT_OK
    with sessions() as session:
        assert session.get(DailyWorldProjectionRepairAudit, 100).status == "restored"


def test_restore_fences_a_same_game_audit_created_after_preflight(
    temp_db_file, tmp_path: Path, monkeypatch
) -> None:
    """The game lock closes the preflight-to-restore audit creation race."""

    engine, _database_path = temp_db_file
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        game_id = _seed_game(session, _candidate_state("restore-lock-fence"))
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
            stdout=StringIO(),
            stderr=StringIO(),
        )
        == cli.EXIT_OK
    )
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        audit.status = "complete"
        audit_id = int(audit.audit_id)
        session.commit()

    entered_lock = threading.Event()
    release_lock = threading.Event()
    thread_errors: list[BaseException] = []
    results: list[int] = []
    original_lock_game = cli._lock_game

    def pause_before_lock(db, locked_game_id):
        if locked_game_id == game_id and not entered_lock.is_set():
            entered_lock.set()
            assert release_lock.wait(5)
        return original_lock_game(db, locked_game_id)

    monkeypatch.setattr(cli, "_lock_game", pause_before_lock)

    def restore() -> None:
        try:
            results.append(
                cli.run(
                    [
                        "--restore-audit-id",
                        str(audit_id),
                        "--expected-report-hash",
                        report.hash,
                        "--confirm-writers-stopped",
                    ],
                    session_factory=sessions,
                    stdout=StringIO(),
                    stderr=StringIO(),
                )
            )
        except BaseException as exc:  # pragma: no cover - surfaced below
            thread_errors.append(exc)

    restore_thread = threading.Thread(target=restore)
    restore_thread.start()
    assert entered_lock.wait(5)
    with sessions() as session:
        audit = session.get(DailyWorldProjectionRepairAudit, audit_id)
        session.add(_clone_audit(audit, audit_id=audit_id + 1, game_id=game_id))
        session.commit()
        state_count_before = session.query(GameState).count()
        projection_statuses_before = [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ]
    release_lock.set()
    restore_thread.join(5)

    assert not thread_errors
    assert results == [cli.EXIT_INVARIANT]
    with sessions() as session:
        assert session.query(GameState).count() == state_count_before
        assert (
            session.get(DailyWorldProjectionRepairAudit, audit_id).status == "complete"
        )
        assert [
            row.status
            for row in session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.projection_id)
            .all()
        ] == projection_statuses_before


def test_restore_then_blocked_state_save_rebases_to_restored_projection(
    temp_db_file, tmp_path: Path, monkeypatch
) -> None:
    from config.feature_flags import reset_features, set_feature
    from src.database.state_repository import StateRepository

    engine, _database_path = temp_db_file
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        game_id = _seed_game(session, _candidate_state("restore-save-race"))
    report = scan_latest_game_states(sessions)
    assert (
        cli.run(
            [
                "--apply",
                "--expected-report-hash",
                report.hash,
                "--backup-dir",
                str(tmp_path),
                "--wait",
            ],
            session_factory=sessions,
            projection_service=CompletingProjectionWake(sessions, game_id),
            stdout=StringIO(),
            stderr=StringIO(),
        )
        == cli.EXIT_OK
    )
    with sessions() as session:
        audit = session.query(DailyWorldProjectionRepairAudit).one()
        audit_id = int(audit.audit_id)
        stale_repaired = PlayerState.from_dict(
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
            .state_json
        )
        original = restore_state_backup(
            audit.backup_path,
            audit.backup_sha256,
            expected_game_id=game_id,
            expected_state_id=audit.state_id,
        )

    entered_locked_restore = threading.Event()
    release_restore = threading.Event()
    save_done = threading.Event()
    results: list[object] = []
    original_match = cli.rebuild_identities_match_history
    calls = 0

    def pause_second_history_check(identities, state):
        nonlocal calls
        calls += 1
        result = original_match(identities, state)
        if calls == 2:
            entered_locked_restore.set()
            assert release_restore.wait(5)
        return result

    monkeypatch.setattr(
        cli, "rebuild_identities_match_history", pause_second_history_check
    )
    import src.database.state_repository as state_repository_module

    monkeypatch.setattr(state_repository_module, "SessionLocal", sessions)

    def restore() -> None:
        results.append(
            cli.run(
                [
                    "--restore-audit-id",
                    str(audit_id),
                    "--expected-report-hash",
                    report.hash,
                    "--confirm-writers-stopped",
                ],
                session_factory=sessions,
                stdout=StringIO(),
                stderr=StringIO(),
            )
        )

    def save() -> None:
        results.append(StateRepository().save_game_progress(game_id, stale_repaired))
        save_done.set()

    set_feature("daily_world_projection_v1", True)
    try:
        restore_thread = threading.Thread(target=restore)
        restore_thread.start()
        assert entered_locked_restore.wait(5)
        save_thread = threading.Thread(target=save)
        save_thread.start()
        assert save_done.wait(0.2) is False
        release_restore.set()
        restore_thread.join(5)
        save_thread.join(5)
    finally:
        reset_features()

    assert sorted(results, key=str) == [0, True]
    latest = _db_snapshot(sessions)["states"][-1][2]
    assert latest["world_projection_state"] == original["world_projection_state"]
