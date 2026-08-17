from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime

import pytest
from sqlalchemy.orm import sessionmaker

from config.feature_flags import reset_features, set_feature
from src.ai.models import EventOption, GameEvent
from src.api.session_store import session_store
from src.database.models import (
    DailyWorldProjection,
    DailyWorldProjectionRepairAudit,
    Game,
    GameState,
)
from src.database.state_repository import StateRepository
from src.game.daily_timeline import build_daily_timeline
from src.game.game_loop import GameLoop
from src.game.round.daily_choice_processor import DailyChoiceProcessor
from src.game.state import PlayerState
from src.game.world_projection_schema import compute_projection_source_hash
from src.services.daily_world_projection import DailyWorldProjectionService
from src.services.daily_world_projection_backup import write_state_backup
from src.services.daily_world_projection_repair import (
    finalize_repair_audit,
    non_projection_state_digest,
)
from src.services.daily_world_projection_repository import (
    DailyWorldProjectionRepository,
)

pytestmark = [pytest.mark.unit]



def _record(day: int, *, status: str = "pending") -> dict:
    story = f"第 {day} 天，孙悟空从花果山前往第 {day} 号地点。"
    options = [
        {"text": "继续前进", "effects": {}},
        {"text": "原地休息", "effects": {}},
    ]
    return {
        "event_id": f"event-{day}",
        "revision": 1,
        "day_index": day,
        "story_date": f"2026-08-{day + 1:02d}",
        "event_description": story,
        "options": options,
        "choice_option_index": 0,
        "choice": "继续前进",
        "world_projection_status": status,
        "postprocessing_status": "complete",
    }


def _projection(game_id: int, record: dict, status: str) -> DailyWorldProjection:
    return DailyWorldProjection(
        game_id=game_id,
        event_id=record["event_id"],
        revision=record["revision"],
        day_index=record["day_index"],
        story_date=record["story_date"],
        source_hash=compute_projection_source_hash(
            record["event_description"], record["options"]
        ),
        status=status,
        story_patch_json={
            "fact_updates": [
                {
                    "action": "new",
                    "subject": f"day-{record['day_index']}",
                    "category": "situation",
                    "fact": f"day-{record['day_index']}-applied",
                }
            ]
        },
        option_patches_json={"0": {}, "1": {}},
        next_attempt_at=datetime.utcnow(),
    )


def _seed_game(
    engine, *, days=(5, 6, 7), statuses=("ready", "failed_retryable", "ready")
):
    Session = sessionmaker(bind=engine)
    with Session.begin() as db:
        game = Game(language="zh", initial_state={})
        db.add(game)
        db.flush()
        records = [_record(day) for day in days]
        state = PlayerState(
            week=1,
            timeline=build_daily_timeline(
                start_date="2026-08-01", day_index=max(days) + 1
            ),
            timeline_version=2,
            day_history=records,
        )
        state.world_projection_state["applied_through_day_index"] = min(days) - 1
        db.add(
            GameState(
                game_id=game.game_id,
                week=state.week,
                age=state.age,
                state_json=state.to_dict(),
            )
        )
        for record, status in zip(records, statuses):
            db.add(_projection(game.game_id, record, status))
        return game.game_id, Session


def _latest(Session, game_id: int) -> dict:
    with Session() as db:
        return (
            db.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
            .state_json
        )


def test_serial_applier_stops_at_failed_gap_day_6(temp_db_file) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine)
    service = DailyWorldProjectionService(session_factory=Session)

    assert service.apply_ready_for_game(game_id) == 1

    saved = _latest(Session, game_id)
    assert saved["world_projection_state"]["applied_through_day_index"] == 5
    assert [
        item["fact"]
        for item in saved["world_projection_state"]["world"]["fact_updates"]
    ] == ["day-5-applied"]
    with Session() as db:
        statuses = {
            row.day_index: row.status
            for row in db.query(DailyWorldProjection).order_by(
                DailyWorldProjection.day_index
            )
        }
    assert statuses == {5: "applied", 6: "failed_retryable", 7: "ready"}


def test_state_save_failure_keeps_projection_ready_and_original_state(
    temp_db_file,
) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine, days=(5,), statuses=("ready",))

    def fail_save() -> None:
        raise RuntimeError("injected_state_save_failure")

    service = DailyWorldProjectionService(
        session_factory=Session, before_projection_state_save=fail_save
    )

    with pytest.raises(RuntimeError, match="injected_state_save_failure"):
        service.apply_ready_for_game(game_id)

    assert (
        _latest(Session, game_id)["world_projection_state"]["applied_through_day_index"]
        == 4
    )
    with Session() as db:
        assert db.query(DailyWorldProjection).one().status == "ready"


def test_mark_applied_failure_replays_saved_source_without_duplicate_materialization(
    temp_db_file,
) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine, days=(5,), statuses=("ready",))

    class FailOnceRepository(DailyWorldProjectionRepository):
        failures = 1

        def mark_applied(self, *args, **kwargs):
            if type(self).failures:
                type(self).failures -= 1
                return False
            return super().mark_applied(*args, **kwargs)

    service = DailyWorldProjectionService(
        session_factory=Session, repository_factory=FailOnceRepository
    )

    assert service.apply_ready_for_game(game_id) == 1
    first = _latest(Session, game_id)
    assert service.run_once() == 0
    second = _latest(Session, game_id)

    assert second["world_projection_state"] == first["world_projection_state"]
    assert len(second["world_projection_state"]["world"]["fact_updates"]) == 1
    with Session() as db:
        assert db.query(DailyWorldProjection).one().status == "applied"


def test_absent_choice_projection_is_reconciled_from_reloaded_pending_history(
    temp_db_file, monkeypatch
) -> None:
    engine, _ = temp_db_file
    Session = sessionmaker(bind=engine)
    with Session.begin() as db:
        game = Game(language="zh", initial_state={})
        db.add(game)
        db.flush()
        game_id = game.game_id
    state = PlayerState(
        timeline=build_daily_timeline(start_date="2026-08-01", day_index=0),
        timeline_version=2,
    )
    event = GameEvent(
        event_id="event-0",
        revision=1,
        story_date="2026-08-01",
        event_description="孙悟空离开花果山，前往东海。",
        options=[
            EventOption(text="启程", effects={}),
            EventOption(text="留下", effects={}),
        ],
    )
    holder = {"event": event}
    processor = DailyChoiceProcessor(
        player_state_getter=lambda: state,
        current_event_getter=lambda: holder["event"],
        current_event_setter=lambda value: holder.__setitem__("event", value),
        projection_lookup=lambda **_identity: None,
    )

    def persist(candidate) -> bool:
        with Session.begin() as db:
            db.add(
                GameState(
                    game_id=game_id,
                    week=candidate.week,
                    age=candidate.age,
                    state_json=candidate.to_dict(),
                )
            )
        return True

    processor.make_choice(
        event_id="event-0", revision=1, option_index=0, persist_callback=persist
    )
    loaded = PlayerState.from_dict(_latest(Session, game_id))
    service = DailyWorldProjectionService(session_factory=Session)
    monkeypatch.setattr(
        "src.services.daily_world_projection.get_daily_world_projection_service",
        lambda: service,
    )
    loop = object.__new__(GameLoop)
    loop.player_state = loaded
    loop.current_event = None

    set_feature("daily_world_projection_v1", True)
    try:
        loop._reconcile_daily_world_projections({"_game_id": game_id})
    finally:
        reset_features()

    with Session() as db:
        row = db.query(DailyWorldProjection).one()
        assert (row.event_id, row.revision, row.day_index, row.status) == (
            "event-0",
            1,
            0,
            "pending",
        )


def test_concurrent_worker_and_choice_preserve_one_projection_application(
    temp_db_file,
) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine, days=(5,), statuses=("ready",))
    base = PlayerState.from_dict(_latest(Session, game_id))
    base.timeline = build_daily_timeline(start_date="2026-08-01", day_index=5)
    base.day_history = []
    event = GameEvent(
        event_id="event-5",
        revision=1,
        story_date=base.timeline["current_date"],
        event_description=_record(5)["event_description"],
        options=[
            EventOption(text="继续前进", effects={}),
            EventOption(text="原地休息", effects={}),
        ],
    )
    with Session.begin() as db:
        db.query(DailyWorldProjection).filter(
            DailyWorldProjection.game_id == game_id
        ).update(
            {
                DailyWorldProjection.source_hash: compute_projection_source_hash(
                    event.event_description, event.options
                )
            },
            synchronize_session=False,
        )
    holder = {"event": event}
    service = DailyWorldProjectionService(session_factory=Session)

    def lookup(**identity):
        return service.lookup_choice_projection(**identity)

    processor = DailyChoiceProcessor(
        player_state_getter=lambda: base,
        current_event_getter=lambda: holder["event"],
        current_event_setter=lambda value: holder.__setitem__("event", value),
        game_id_getter=lambda: game_id,
        projection_lookup=lookup,
    )

    def persist(candidate) -> bool:
        with Session.begin() as db:
            db.add(
                GameState(
                    game_id=game_id,
                    week=candidate.week,
                    age=candidate.age,
                    state_json=candidate.to_dict(),
                )
            )
        return True

    barrier = threading.Barrier(2)
    errors = []

    def run_worker():
        try:
            barrier.wait()
            service.apply_ready_for_game(game_id)
        except Exception as exc:  # pragma: no cover - assertion below reports it
            errors.append(exc)

    thread = threading.Thread(target=run_worker)
    thread.start()
    barrier.wait()
    processor.make_choice(
        event_id="event-5", revision=1, option_index=0, persist_callback=persist
    )
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert errors == []
    saved = _latest(Session, game_id)
    assert len(saved["world_projection_state"]["world"]["fact_updates"]) == 1
    assert len(saved["world_projection_state"]["applied_sources"]) == 1


def test_serial_applier_updates_live_session_and_uses_its_mutation_lock(
    temp_db_file,
) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine, days=(5,), statuses=("ready",))
    loop = object.__new__(GameLoop)
    loop.player_state = PlayerState.from_dict(_latest(Session, game_id))
    attempted = threading.Event()
    underlying_lock = threading.RLock()

    class ObservedLock:
        def __enter__(self):
            attempted.set()
            underlying_lock.acquire()
            return self

        def __exit__(self, *_args):
            underlying_lock.release()

    loop._daily_mutation_lock = ObservedLock()
    session_store.put(game_id, loop, user_id=99156)
    service = DailyWorldProjectionService(session_factory=Session)
    finished = threading.Event()

    try:
        with loop._daily_mutation_lock:
            attempted.clear()
            worker = threading.Thread(
                target=lambda: (service.apply_ready_for_game(game_id), finished.set())
            )
            worker.start()
            assert attempted.wait(timeout=5)
            assert not finished.is_set()
        worker.join(timeout=5)

        assert not worker.is_alive()
        assert (
            loop.player_state.world_projection_state["applied_through_day_index"] == 5
        )
        assert (
            len(loop.player_state.world_projection_state["world"]["fact_updates"]) == 1
        )
    finally:
        session_store.remove(game_id, user_id=99156)


def test_serial_applier_includes_session_registered_during_database_apply(
    temp_db_file,
) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine, days=(5,), statuses=("ready",))
    stale_state = PlayerState.from_dict(_latest(Session, game_id))
    loop = object.__new__(GameLoop)
    loop.player_state = stale_state
    loop._daily_mutation_lock = threading.RLock()
    service = DailyWorldProjectionService(session_factory=Session)
    snapshot_taken = threading.Event()
    release_apply = threading.Event()
    original_active = service._active_game_loops
    calls = 0

    def active_loops(requested_game_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            snapshot_taken.set()
            assert release_apply.wait(timeout=5)
            return []
        return original_active(requested_game_id)

    service._active_game_loops = active_loops
    worker = threading.Thread(target=lambda: service.apply_ready_for_game(game_id))
    worker.start()
    assert snapshot_taken.wait(timeout=5)
    session_store.put(game_id, loop, user_id=88156)
    release_apply.set()
    worker.join(timeout=5)

    try:
        assert not worker.is_alive()
        assert (
            loop.player_state.world_projection_state["applied_through_day_index"] == 5
        )
        assert (
            len(loop.player_state.world_projection_state["world"]["fact_updates"]) == 1
        )
    finally:
        session_store.remove(game_id, user_id=88156)


def test_choice_projection_lookup_is_strictly_scoped_to_game(temp_db_file) -> None:
    engine, _ = temp_db_file
    Session = sessionmaker(bind=engine)
    record = _record(0)
    with Session.begin() as db:
        game_a = Game(language="zh", initial_state={})
        game_b = Game(language="zh", initial_state={})
        db.add_all((game_a, game_b))
        db.flush()
        game_a_id = game_a.game_id
        game_b_id = game_b.game_id
        db.add(_projection(game_b_id, record, "ready"))

    state = PlayerState(
        timeline=build_daily_timeline(start_date="2026-08-01", day_index=0),
        timeline_version=2,
    )
    event = GameEvent(
        event_id=record["event_id"],
        revision=record["revision"],
        story_date=record["story_date"],
        event_description=record["event_description"],
        options=[EventOption(**option) for option in record["options"]],
    )
    holder = {"event": event}
    service = DailyWorldProjectionService(session_factory=Session)
    processor = DailyChoiceProcessor(
        player_state_getter=lambda: state,
        current_event_getter=lambda: holder["event"],
        current_event_setter=lambda value: holder.__setitem__("event", value),
        game_id_getter=lambda: game_a_id,
        projection_lookup=service.lookup_choice_projection,
    )

    processor.make_choice(
        event_id=event.event_id,
        revision=event.revision,
        option_index=0,
    )

    assert game_a_id != game_b_id
    assert state.day_history[-1]["world_projection_status"] == "pending"
    assert state.world_projection_state["world"]["fact_updates"] == []


def test_choice_save_revalidates_projection_after_lookup_supersede(
    temp_db_file, monkeypatch
) -> None:
    engine, _ = temp_db_file
    Session = sessionmaker(bind=engine)
    record = _record(0)
    state = PlayerState(
        timeline=build_daily_timeline(start_date="2026-08-01", day_index=0),
        timeline_version=2,
    )
    with Session.begin() as db:
        game = Game(language="zh", initial_state=state.to_dict())
        db.add(game)
        db.flush()
        game_id = game.game_id
        db.add(
            GameState(
                game_id=game_id,
                week=state.week,
                age=state.age,
                state_json=state.to_dict(),
            )
        )
        db.add(_projection(game_id, record, "ready"))
    event = GameEvent(
        event_id=record["event_id"],
        revision=record["revision"],
        story_date=record["story_date"],
        event_description=record["event_description"],
        options=[EventOption(**option) for option in record["options"]],
    )
    holder = {"event": event}
    service = DailyWorldProjectionService(session_factory=Session)

    def lookup_then_supersede(**identity):
        snapshot = service.lookup_choice_projection(**identity)
        with Session.begin() as db:
            db.query(DailyWorldProjection).filter(
                DailyWorldProjection.game_id == game_id
            ).update({"status": "superseded"}, synchronize_session=False)
        return snapshot

    import src.database.state_repository as state_repository_module

    monkeypatch.setattr(state_repository_module, "SessionLocal", Session)
    set_feature("daily_world_projection_v1", True)
    try:
        processor = DailyChoiceProcessor(
            player_state_getter=lambda: state,
            current_event_getter=lambda: holder["event"],
            current_event_setter=lambda value: holder.__setitem__("event", value),
            game_id_getter=lambda: game_id,
            projection_lookup=lookup_then_supersede,
        )
        processor.make_choice(
            event_id=event.event_id,
            revision=event.revision,
            option_index=0,
            persist_callback=lambda candidate: StateRepository().save_game_progress(
                game_id, candidate
            ),
        )
    finally:
        reset_features()

    assert state.day_history[-1]["world_projection_status"] == "pending"
    assert state.world_projection_state["world"]["fact_updates"] == []
    assert (
        _latest(Session, game_id)["world_projection_state"]["world"]["fact_updates"]
        == []
    )


def test_choice_save_downgrades_incomplete_ready_option_patch_to_pending(
    temp_db_file, monkeypatch
) -> None:
    engine, _ = temp_db_file
    Session = sessionmaker(bind=engine)
    record = _record(0)
    state = PlayerState(
        timeline=build_daily_timeline(start_date="2026-08-01", day_index=0),
        timeline_version=2,
    )
    with Session.begin() as db:
        game = Game(language="zh", initial_state=state.to_dict())
        db.add(game)
        db.flush()
        game_id = game.game_id
        db.add(
            GameState(
                game_id=game_id,
                week=state.week,
                age=state.age,
                state_json=state.to_dict(),
            )
        )
        row = _projection(game_id, record, "ready")
        row.option_patches_json = {"1": {}}
        db.add(row)
    event = GameEvent(
        event_id=record["event_id"],
        revision=record["revision"],
        story_date=record["story_date"],
        event_description=record["event_description"],
        options=[EventOption(**option) for option in record["options"]],
    )
    holder = {"event": event}
    service = DailyWorldProjectionService(session_factory=Session)
    import src.database.state_repository as state_repository_module

    monkeypatch.setattr(state_repository_module, "SessionLocal", Session)
    set_feature("daily_world_projection_v1", True)
    try:
        processor = DailyChoiceProcessor(
            player_state_getter=lambda: state,
            current_event_getter=lambda: holder["event"],
            current_event_setter=lambda value: holder.__setitem__("event", value),
            game_id_getter=lambda: game_id,
            projection_lookup=service.lookup_choice_projection,
        )
        result = processor.make_choice(
            event_id=event.event_id,
            revision=event.revision,
            option_index=0,
            persist_callback=lambda candidate: StateRepository().save_game_progress(
                game_id, candidate
            ),
        )
    finally:
        reset_features()

    assert result["next_timeline"]["day_index"] == 1
    assert state.day_history[-1]["world_projection_status"] == "pending"
    assert state.world_projection_state["world"]["fact_updates"] == []
    assert (
        _latest(Session, game_id)["day_history"][-1]["world_projection_status"]
        == "pending"
    )


def test_normal_save_cannot_overwrite_cross_process_projection_apply(
    temp_db_file, monkeypatch
) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine, days=(0,), statuses=("ready",))
    stale_candidate = PlayerState.from_dict(_latest(Session, game_id))
    service = DailyWorldProjectionService(session_factory=Session)
    assert service.apply_ready_for_game(game_id) == 1

    import src.database.state_repository as state_repository_module

    monkeypatch.setattr(state_repository_module, "SessionLocal", Session)
    set_feature("daily_world_projection_v1", True)
    try:
        assert StateRepository().save_game_progress(game_id, stale_candidate) is True
    finally:
        reset_features()

    saved = _latest(Session, game_id)
    assert saved["world_projection_state"]["applied_through_day_index"] == 0
    assert [
        item["fact"]
        for item in saved["world_projection_state"]["world"]["fact_updates"]
    ] == ["day-0-applied"]
    assert saved["day_history"][0]["world_projection_status"] == "applied"
    assert saved["day_history"][0]["world_projection_id"] > 0
    assert saved["day_history"][0]["world_projection_identity"]["event_id"] == (
        "event-0"
    )


def test_normal_save_before_repair_finalize_preserves_projection_only_history(
    temp_db_file, tmp_path, monkeypatch
) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine, days=(0,), statuses=("ready",))
    with Session.begin() as db:
        latest = (
            db.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
        )
        original = deepcopy(latest.state_json)
        original["day_history"][0].pop("world_projection_status", None)
        latest.state_json = deepcopy(original)
        state_id = int(latest.state_id)
        record = original["day_history"][0]
        source_hash = compute_projection_source_hash(
            record["event_description"], record["options"]
        )
        backup = write_state_backup(
            tmp_path,
            game_id=game_id,
            state_id=state_id,
            state_json=original,
        )
        audit = DailyWorldProjectionRepairAudit(
            game_id=game_id,
            state_id=state_id,
            report_hash="a" * 64,
            backup_path=str(backup.path),
            backup_sha256=backup.sha256,
            non_projection_digest_before=non_projection_state_digest(original),
            status="queued",
            detail_json={
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
            },
        )
        db.add(audit)
        db.flush()
        audit_id = int(audit.audit_id)
        projection = db.query(DailyWorldProjection).one()
        projection.repair_audit_id = audit_id
        projection.repair_selected_option_index = 0

    stale_candidate = PlayerState.from_dict(original)
    assert (
        DailyWorldProjectionService(session_factory=Session).apply_ready_for_game(
            game_id
        )
        == 1
    )

    import src.database.state_repository as state_repository_module

    monkeypatch.setattr(state_repository_module, "SessionLocal", Session)
    set_feature("daily_world_projection_v1", True)
    try:
        assert StateRepository().save_game_progress(game_id, stale_candidate) is True
    finally:
        reset_features()

    saved = _latest(Session, game_id)
    assert non_projection_state_digest(saved) == non_projection_state_digest(original)
    record_after = saved["day_history"][0]
    assert "world_projection_status" not in record_after
    assert "world_projection_id" not in record_after
    assert "world_projection_identity" not in record_after
    assert finalize_repair_audit(Session, audit_id).status == "complete"


def test_normal_save_rejects_choice_conflicting_with_applied_projection(
    temp_db_file, monkeypatch
) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine, days=(0,), statuses=("ready",))
    stale_candidate = PlayerState.from_dict(_latest(Session, game_id))
    service = DailyWorldProjectionService(session_factory=Session)
    assert service.apply_ready_for_game(game_id) == 1
    stale_candidate.day_history[0]["choice_option_index"] = 1

    import src.database.state_repository as state_repository_module

    monkeypatch.setattr(state_repository_module, "SessionLocal", Session)
    set_feature("daily_world_projection_v1", True)
    try:
        assert StateRepository().save_game_progress(game_id, stale_candidate) is False
    finally:
        reset_features()

    saved = _latest(Session, game_id)
    assert saved["day_history"][0]["choice_option_index"] == 0
    assert saved["day_history"][0]["world_projection_status"] == "applied"


def test_legacy_daily_history_establishes_projection_migration_baseline(
    monkeypatch,
) -> None:
    state = PlayerState(
        timeline=build_daily_timeline(start_date="2026-08-01", day_index=2),
        timeline_version=2,
        day_history=[_record(0), _record(1)],
    )
    for record in state.day_history:
        record.pop("world_projection_status", None)
    current = GameEvent(
        event_id="event-2",
        revision=1,
        story_date="2026-08-03",
        event_description="孙悟空回到花果山。",
        options=[
            EventOption(text="休息", effects={}),
            EventOption(text="巡山", effects={}),
        ],
    )
    state.current_event_data = current.model_dump()
    loop = object.__new__(GameLoop)
    loop.player_state = state
    loop.current_event = current
    enqueued = []
    monkeypatch.setattr(
        "src.services.daily_world_projection.enqueue_accepted_daily_world_projection",
        lambda *args, **kwargs: enqueued.append((args, kwargs)) or True,
    )
    set_feature("daily_world_projection_v1", True)
    try:
        loop._reconcile_daily_world_projections({"_game_id": 91})
    finally:
        reset_features()

    assert state.world_projection_state["applied_through_day_index"] == 1
    assert state.world_projection_state["projected_through_day_index"] == 1
    assert len(enqueued) == 1
    assert enqueued[0][0][1] is current
    assert enqueued[0][1] == {"replacement": True}


def test_legacy_projection_migration_baseline_survives_first_save(
    temp_db_file, monkeypatch
) -> None:
    engine, _ = temp_db_file
    Session = sessionmaker(bind=engine)
    legacy_records = [_record(0), _record(1)]
    for record in legacy_records:
        record.pop("world_projection_status", None)
    pending_record = _record(2)
    state = PlayerState(
        week=1,
        timeline=build_daily_timeline(start_date="2026-08-01", day_index=3),
        timeline_version=2,
        day_history=[*legacy_records, pending_record],
    )
    with Session.begin() as db:
        game = Game(language="zh", initial_state={})
        db.add(game)
        db.flush()
        game_id = int(game.game_id)
        db.add(
            GameState(
                game_id=game_id,
                week=1,
                age=18,
                state_json=state.to_dict(),
            )
        )
        db.add(_projection(game_id, pending_record, "ready"))

    loop = object.__new__(GameLoop)
    loop.player_state = PlayerState.from_dict(state.to_dict())
    loop._initialize_projection_migration_baseline()
    assert loop.player_state.world_projection_state["applied_through_day_index"] == 1

    import src.database.state_repository as state_repository_module

    monkeypatch.setattr(state_repository_module, "SessionLocal", Session)
    set_feature("daily_world_projection_v1", True)
    try:
        assert StateRepository().save_game_progress(game_id, loop.player_state) is True
    finally:
        reset_features()

    saved = _latest(Session, game_id)
    assert saved["world_projection_state"]["applied_through_day_index"] == 2
    assert saved["world_projection_state"]["pending_from_day_index"] is None
    assert [
        item["fact"]
        for item in saved["world_projection_state"]["world"]["fact_updates"]
    ] == ["day-2-applied"]
    assert (
        DailyWorldProjectionService(session_factory=Session).apply_ready_for_game(
            game_id
        )
        == 0
    )
    with Session() as db:
        assert db.query(DailyWorldProjection).one().status == "applied"
    replayed = _latest(Session, game_id)
    assert [
        item["fact"]
        for item in replayed["world_projection_state"]["world"]["fact_updates"]
    ] == ["day-2-applied"]


def test_legacy_projection_baseline_does_not_skip_an_existing_ready_row(
    temp_db_file, monkeypatch
) -> None:
    engine, _ = temp_db_file
    Session = sessionmaker(bind=engine)
    record = _record(0)
    record.pop("world_projection_status", None)
    state = PlayerState(
        week=1,
        timeline=build_daily_timeline(start_date="2026-08-01", day_index=1),
        timeline_version=2,
        day_history=[record],
    )
    with Session.begin() as db:
        game = Game(language="zh", initial_state={})
        db.add(game)
        db.flush()
        game_id = int(game.game_id)
        db.add(
            GameState(
                game_id=game_id,
                week=1,
                age=18,
                state_json=state.to_dict(),
            )
        )
        db.add(_projection(game_id, record, "ready"))

    import src.database.state_repository as state_repository_module

    monkeypatch.setattr(state_repository_module, "SessionLocal", Session)
    set_feature("daily_world_projection_v1", True)
    try:
        assert StateRepository().save_game_progress(game_id, state) is True
    finally:
        reset_features()

    saved = _latest(Session, game_id)
    assert saved["world_projection_state"]["applied_through_day_index"] == 0
    assert [
        item["fact"]
        for item in saved["world_projection_state"]["world"]["fact_updates"]
    ] == ["day-0-applied"]


def test_projection_reconciliation_is_a_noop_while_feature_is_disabled(
    monkeypatch,
) -> None:
    state = PlayerState(
        timeline=build_daily_timeline(start_date="2026-08-01", day_index=1),
        timeline_version=2,
        day_history=[_record(0)],
    )
    state.day_history[0].pop("world_projection_status", None)
    loop = object.__new__(GameLoop)
    loop.player_state = state
    loop.current_event = None
    enqueued = []
    monkeypatch.setattr(
        "src.services.daily_world_projection.enqueue_accepted_daily_world_projection",
        lambda *args, **kwargs: enqueued.append((args, kwargs)) or True,
    )
    reset_features()

    loop._reconcile_daily_world_projections({"_game_id": 91})

    assert state.world_projection_state["applied_through_day_index"] == -1
    assert enqueued == []


def test_save_point_rewind_preserves_older_projection_layer(
    temp_db_file, monkeypatch
) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine, days=(0,), statuses=("ready",))
    service = DailyWorldProjectionService(session_factory=Session)
    assert service.apply_ready_for_game(game_id) == 1
    day_zero = _latest(Session, game_id)
    with Session.begin() as db:
        save_point = GameState(
            game_id=game_id,
            week=1,
            age=18,
            state_json=day_zero,
            is_save_point=True,
            save_name="day-zero",
        )
        db.add(save_point)
        db.flush()
        save_point_id = int(save_point.state_id)
        day_one_state = PlayerState.from_dict(day_zero)
        day_one_state.day_history.append(_record(1))
        day_one_state.timeline = build_daily_timeline(
            start_date="2026-08-01", day_index=2
        )
        db.add(
            GameState(
                game_id=game_id,
                week=1,
                age=18,
                state_json=day_one_state.to_dict(),
            )
        )
        db.add(_projection(game_id, day_one_state.day_history[-1], "ready"))
    assert service.apply_ready_for_game(game_id) == 1

    rewound = PlayerState.from_dict(day_zero)
    rewound.world_projection_state["rewind_from_state_id"] = save_point_id
    import src.database.state_repository as state_repository_module

    monkeypatch.setattr(state_repository_module, "SessionLocal", Session)
    set_feature("daily_world_projection_v1", True)
    try:
        assert StateRepository().save_game_progress(game_id, rewound) is True
    finally:
        reset_features()

    saved = _latest(Session, game_id)
    assert saved["world_projection_state"]["applied_through_day_index"] == 0
    assert [
        item["fact"]
        for item in saved["world_projection_state"]["world"]["fact_updates"]
    ] == ["day-0-applied"]
    assert "rewind_from_state_id" not in saved["world_projection_state"]
    with Session() as db:
        day_one = (
            db.query(DailyWorldProjection)
            .filter(
                DailyWorldProjection.game_id == game_id,
                DailyWorldProjection.day_index == 1,
            )
            .one()
        )
        assert day_one.status == "superseded"


def test_save_point_rewind_resets_the_saved_current_event_for_reprojection(
    temp_db_file, monkeypatch
) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine, days=(0,), statuses=("ready",))
    service = DailyWorldProjectionService(session_factory=Session)
    assert service.apply_ready_for_game(game_id) == 1
    day_zero = _latest(Session, game_id)
    current_record = _record(1)
    current_event = GameEvent(
        event_id=current_record["event_id"],
        revision=current_record["revision"],
        story_date=current_record["story_date"],
        event_description=current_record["event_description"],
        options=[EventOption(**option) for option in current_record["options"]],
    )
    save_point_state = PlayerState.from_dict(day_zero)
    save_point_state.current_event_data = current_event.model_dump()
    save_point_state.timeline = build_daily_timeline(
        start_date="2026-08-01", day_index=1
    )
    with Session.begin() as db:
        save_point = GameState(
            game_id=game_id,
            week=1,
            age=18,
            state_json=save_point_state.to_dict(),
            is_save_point=True,
            save_name="before-day-one-choice",
        )
        db.add(save_point)
        db.flush()
        save_point_id = int(save_point.state_id)
        future = PlayerState.from_dict(save_point_state.to_dict())
        future.current_event_data = None
        future.day_history.append(current_record)
        future.timeline = build_daily_timeline(start_date="2026-08-01", day_index=2)
        db.add(
            GameState(
                game_id=game_id,
                week=1,
                age=18,
                state_json=future.to_dict(),
            )
        )
        db.add(_projection(game_id, current_record, "ready"))
    assert service.apply_ready_for_game(game_id) == 1

    rewound = PlayerState.from_dict(save_point_state.to_dict())
    rewound.world_projection_state["rewind_from_state_id"] = save_point_id
    import src.database.state_repository as state_repository_module

    monkeypatch.setattr(state_repository_module, "SessionLocal", Session)
    set_feature("daily_world_projection_v1", True)
    try:
        assert StateRepository().save_game_progress(game_id, rewound) is True
    finally:
        reset_features()

    saved = _latest(Session, game_id)
    assert saved["current_event_data"]["event_id"] == "event-1"
    assert saved["world_projection_state"]["applied_through_day_index"] == 0
    with Session() as db:
        replay = (
            db.query(DailyWorldProjection)
            .filter(
                DailyWorldProjection.game_id == game_id,
                DailyWorldProjection.day_index == 1,
            )
            .one()
        )
        assert replay.status == "pending"
        assert replay.story_patch_json is None
        assert replay.option_patches_json is None


def test_save_point_rewind_preserves_pending_settled_days_before_current_event(
    temp_db_file, monkeypatch
) -> None:
    engine, _ = temp_db_file
    game_id, Session = _seed_game(engine, days=(0,), statuses=("ready",))
    service = DailyWorldProjectionService(session_factory=Session)
    assert service.apply_ready_for_game(game_id) == 1
    save_point_state = PlayerState.from_dict(_latest(Session, game_id))
    pending_record = _record(1)
    current_record = _record(2)
    current_event = GameEvent(
        event_id=current_record["event_id"],
        revision=current_record["revision"],
        story_date=current_record["story_date"],
        event_description=current_record["event_description"],
        options=[EventOption(**option) for option in current_record["options"]],
    )
    save_point_state.day_history.append(pending_record)
    save_point_state.current_event_data = current_event.model_dump()
    save_point_state.timeline = build_daily_timeline(
        start_date="2026-08-01", day_index=2
    )
    with Session.begin() as db:
        save_point = GameState(
            game_id=game_id,
            week=1,
            age=18,
            state_json=save_point_state.to_dict(),
            is_save_point=True,
            save_name="pending-day-before-current",
        )
        db.add(save_point)
        db.flush()
        save_point_id = int(save_point.state_id)
        db.add(_projection(game_id, pending_record, "ready"))
        db.add(_projection(game_id, current_record, "ready"))

    rewound = PlayerState.from_dict(save_point_state.to_dict())
    rewound.world_projection_state["rewind_from_state_id"] = save_point_id
    import src.database.state_repository as state_repository_module

    monkeypatch.setattr(state_repository_module, "SessionLocal", Session)
    set_feature("daily_world_projection_v1", True)
    try:
        assert StateRepository().save_game_progress(game_id, rewound) is True
    finally:
        reset_features()

    saved = _latest(Session, game_id)
    assert saved["world_projection_state"]["applied_through_day_index"] == 0
    assert saved["world_projection_state"]["pending_from_day_index"] == 1
    with Session() as db:
        rows = (
            db.query(DailyWorldProjection)
            .filter(DailyWorldProjection.game_id == game_id)
            .order_by(DailyWorldProjection.day_index)
            .all()
        )
        assert [(row.day_index, row.status) for row in rows] == [
            (0, "applied"),
            (1, "pending"),
            (2, "pending"),
        ]
