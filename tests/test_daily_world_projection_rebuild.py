"""Repair rebuild contracts for projection-only state materialization."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from src.database.models import (
    DailyWorldProjection,
    DailyWorldProjectionRepairAudit,
    Game,
    GameState,
)
from src.game.state import PlayerState
from src.game.state.player_data import default_world_projection_state
from src.game.world_projection_schema import compute_projection_source_hash
from src.services.daily_world_projection import DailyWorldProjectionService
from src.services.daily_world_projection_backup import write_state_backup
from src.services.daily_world_projection_repair import (
    non_projection_state_digest,
    repair_projection_only_identities,
)


def _accepted_state() -> dict[str, object]:
    state = PlayerState().to_dict()
    story = "李长庚抵达河岸，履行了与苏禾会面的约定。"
    options = [
        {"text": "与苏禾交谈", "effects": {}},
        {"text": "先观察四周", "effects": {}},
    ]
    state.update(
        {
            "timeline_version": 2,
            "timeline": {
                "version": 2,
                "start_date": "2026-08-17",
                "day_index": 1,
                "current_date": "2026-08-18",
            },
            "day_history": [
                {
                    "event_id": "repair-day-0",
                    "revision": 1,
                    "day_index": 0,
                    "story_date": "2026-08-17",
                    "event_description": story,
                    "options": options,
                    "choice_option_index": 0,
                    "postprocessing_status": "failed",
                }
            ],
            "world_projection_state": default_world_projection_state(),
        }
    )
    return state


def _seed_ready_projection(
    session, *, with_audit: bool, audit_status: str = "queued", backup_root=None
):
    state = _accepted_state()
    history = state["day_history"]
    record = history[0]
    source_hash = compute_projection_source_hash(
        record["event_description"], record["options"]
    )
    game = Game(initial_state=deepcopy(state))
    session.add(game)
    session.flush()
    snapshot = GameState(
        game_id=game.game_id,
        week=int(state["week"]),
        age=int(state["age"]),
        state_json=deepcopy(state),
    )
    session.add(snapshot)
    session.flush()
    projection = DailyWorldProjection(
        game_id=game.game_id,
        event_id=record["event_id"],
        revision=record["revision"],
        day_index=record["day_index"],
        story_date=record["story_date"],
        source_hash=source_hash,
        status="ready_no_change",
        story_patch_json={},
        option_patches_json={"0": {}, "1": {}},
        coverage_json={"result": "no_change"},
        next_attempt_at=datetime.utcnow(),
    )
    session.add(projection)
    session.flush()
    if with_audit:
        assert backup_root is not None
        backup = write_state_backup(
            backup_root,
            game_id=game.game_id,
            state_id=snapshot.state_id,
            state_json=state,
        )
        audit = DailyWorldProjectionRepairAudit(
            game_id=game.game_id,
            state_id=snapshot.state_id,
            report_hash="a" * 64,
            backup_path=str(backup.path),
            backup_sha256=backup.sha256,
            non_projection_digest_before=non_projection_state_digest(state),
            status=audit_status,
            detail_json={
                "rebuild_day_indexes": [record["day_index"]],
                "rebuild_identities": [
                    {
                        "event_id": record["event_id"],
                        "revision": record["revision"],
                        "day_index": record["day_index"],
                        "source_hash": source_hash,
                        "selected_option_index": record["choice_option_index"],
                    }
                ],
            },
        )
        session.add(audit)
        session.flush()
        projection.repair_audit_id = audit.audit_id
        projection.repair_selected_option_index = record["choice_option_index"]
    session.commit()
    return game.game_id, deepcopy(state["day_history"])


def _latest_state(session, game_id: int) -> dict[str, object]:
    row = (
        session.query(GameState)
        .filter(GameState.game_id == game_id)
        .order_by(GameState.state_id.desc())
        .first()
    )
    assert row is not None
    return deepcopy(row.state_json)


def test_failed_repair_audit_keeps_day_history_projection_only(
    db_engine, tmp_path
) -> None:
    """A late worker must honor a durable repair marker after audit failure."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        game_id, history_before = _seed_ready_projection(
            session,
            with_audit=True,
            audit_status="failed_invariant",
            backup_root=tmp_path,
        )
        state_before = _latest_state(session, game_id)
        game_updated_before = session.get(Game, game_id).updated_at

    service = DailyWorldProjectionService(session_factory=sessions)
    assert service.apply_ready_for_game(game_id) == 1

    with sessions() as session:
        state_after = _latest_state(session, game_id)
        projection = session.query(DailyWorldProjection).one()
        game_updated_after = session.get(Game, game_id).updated_at

    assert state_after["day_history"] == history_before
    assert non_projection_state_digest(state_after) == non_projection_state_digest(
        state_before
    )
    assert state_after["world_projection_state"]["applied_through_day_index"] == 0
    assert projection.status == "applied"
    assert game_updated_after == game_updated_before


def test_ordinary_projection_still_writes_pr2_history_metadata(db_engine) -> None:
    """The repair seam must not change ordinary PR2 materialization behavior."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        game_id, history_before = _seed_ready_projection(session, with_audit=False)

    service = DailyWorldProjectionService(session_factory=sessions)
    assert service.apply_ready_for_game(game_id) == 1

    with sessions() as session:
        state_after = _latest_state(session, game_id)

    record = state_after["day_history"][0]
    assert state_after["day_history"] != history_before
    assert record["world_projection_status"] == "applied"
    assert record["world_projection_id"] > 0
    assert record["world_projection_identity"]["event_id"] == "repair-day-0"


def test_restored_and_unverified_audits_have_no_metadata_authority(
    db_engine, tmp_path
) -> None:
    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        game_id, _history_before = _seed_ready_projection(session, with_audit=False)
        snapshot = session.query(GameState).filter_by(game_id=game_id).one()
        state = deepcopy(snapshot.state_json)
        record = state["day_history"][0]
        source_hash = compute_projection_source_hash(
            record["event_description"], record["options"]
        )
        detail = {
            "rebuild_day_indexes": [0],
            "rebuild_identities": [
                {
                    "event_id": record["event_id"],
                    "revision": record["revision"],
                    "day_index": 0,
                    "source_hash": source_hash,
                    "selected_option_index": 0,
                }
            ],
        }
        backup = write_state_backup(
            tmp_path,
            game_id=game_id,
            state_id=snapshot.state_id,
            state_json=state,
        )
        session.add_all(
            [
                DailyWorldProjectionRepairAudit(
                    game_id=game_id,
                    state_id=snapshot.state_id,
                    report_hash="a" * 64,
                    backup_path=str(backup.path),
                    backup_sha256=backup.sha256,
                    non_projection_digest_before=non_projection_state_digest(state),
                    status="restored",
                    detail_json=deepcopy(detail),
                ),
                DailyWorldProjectionRepairAudit(
                    game_id=game_id,
                    state_id=snapshot.state_id,
                    report_hash="b" * 64,
                    backup_path=str(tmp_path / "does-not-exist.json"),
                    backup_sha256="c" * 64,
                    non_projection_digest_before=non_projection_state_digest(state),
                    status="queued",
                    detail_json=deepcopy(detail),
                ),
            ]
        )
        session.commit()
        assert repair_projection_only_identities(session, game_id) == set()

    assert (
        DailyWorldProjectionService(session_factory=sessions).apply_ready_for_game(
            game_id
        )
        == 1
    )
    with sessions() as session:
        record_after = _latest_state(session, game_id)["day_history"][0]
    assert record_after["world_projection_status"] == "applied"
    assert record_after["world_projection_identity"]["event_id"] == "repair-day-0"


def test_repair_option_mismatch_does_not_suppress_history_metadata(
    db_engine, tmp_path
) -> None:
    """Suppression must match the accepted option, not only source revision/hash."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        game_id, _history_before = _seed_ready_projection(
            session, with_audit=True, backup_root=tmp_path
        )
        latest = (
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
        )
        changed = deepcopy(latest.state_json)
        changed["day_history"][0]["choice_option_index"] = 1
        latest.state_json = changed
        session.commit()

    service = DailyWorldProjectionService(session_factory=sessions)
    assert service.apply_ready_for_game(game_id) == 1

    with sessions() as session:
        state_after = _latest_state(session, game_id)

    record = state_after["day_history"][0]
    assert record["choice_option_index"] == 1
    assert record["world_projection_status"] == "applied"
    assert record["world_projection_identity"]["event_id"] == "repair-day-0"


def test_mixed_repair_and_ordinary_batch_preserves_each_history_contract(
    db_engine,
    tmp_path,
) -> None:
    """A repair row must not discard ordinary PR2 metadata from the same batch."""

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        state = _accepted_state()
        second = deepcopy(state["day_history"][0])
        second.update(
            {
                "event_id": "ordinary-day-1",
                "day_index": 1,
                "story_date": "2026-08-18",
                "event_description": "苏禾在第二天抵达山门。",
            }
        )
        state["day_history"].append(second)
        state["timeline"]["day_index"] = 2
        game = Game(initial_state=deepcopy(state))
        session.add(game)
        session.flush()
        snapshot = GameState(
            game_id=game.game_id,
            week=int(state["week"]),
            age=int(state["age"]),
            state_json=deepcopy(state),
        )
        session.add(snapshot)
        session.flush()
        rows = []
        for record in state["day_history"]:
            source_hash = compute_projection_source_hash(
                record["event_description"], record["options"]
            )
            row = DailyWorldProjection(
                game_id=game.game_id,
                event_id=record["event_id"],
                revision=record["revision"],
                day_index=record["day_index"],
                story_date=record["story_date"],
                source_hash=source_hash,
                status="ready_no_change",
                story_patch_json={},
                option_patches_json={"0": {}, "1": {}},
                next_attempt_at=datetime.utcnow(),
            )
            session.add(row)
            rows.append((record, source_hash))
        repair_record, repair_hash = rows[0]
        repair_backup_state = deepcopy(state)
        repair_backup_state["day_history"] = [deepcopy(repair_record)]
        repair_backup_state["timeline"]["day_index"] = 1
        backup = write_state_backup(
            tmp_path,
            game_id=game.game_id,
            state_id=snapshot.state_id,
            state_json=repair_backup_state,
        )
        audit = DailyWorldProjectionRepairAudit(
            game_id=game.game_id,
            state_id=snapshot.state_id,
            report_hash="a" * 64,
            backup_path=str(backup.path),
            backup_sha256=backup.sha256,
            non_projection_digest_before=non_projection_state_digest(state),
            status="queued",
            detail_json={
                "rebuild_day_indexes": [repair_record["day_index"]],
                "rebuild_identities": [
                    {
                        "event_id": repair_record["event_id"],
                        "revision": repair_record["revision"],
                        "day_index": repair_record["day_index"],
                        "source_hash": repair_hash,
                        "selected_option_index": repair_record["choice_option_index"],
                    }
                ],
            },
        )
        session.add(audit)
        session.flush()
        repair_row = (
            session.query(DailyWorldProjection)
            .filter(
                DailyWorldProjection.game_id == game.game_id,
                DailyWorldProjection.day_index == repair_record["day_index"],
            )
            .one()
        )
        repair_row.repair_audit_id = audit.audit_id
        repair_row.repair_selected_option_index = repair_record["choice_option_index"]
        session.commit()
        game_id = int(game.game_id)
        game_updated_before = session.get(Game, game_id).updated_at

    service = DailyWorldProjectionService(session_factory=sessions)
    assert service.apply_ready_for_game(game_id) == 2

    with sessions() as session:
        state_after = _latest_state(session, game_id)
        game_updated_after = session.get(Game, game_id).updated_at
        statuses = {
            row.day_index: row.status
            for row in session.query(DailyWorldProjection).all()
        }

    repair_after, ordinary_after = state_after["day_history"]
    assert "world_projection_status" not in repair_after
    assert ordinary_after["world_projection_status"] == "applied"
    assert ordinary_after["world_projection_identity"]["event_id"] == "ordinary-day-1"
    assert statuses == {0: "applied", 1: "applied"}
    assert game_updated_after > game_updated_before
