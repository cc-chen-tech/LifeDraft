from __future__ import annotations

import threading
from datetime import datetime

import pytest
from sqlalchemy.orm import sessionmaker

from src.ai.models import EventOption, GameEvent
from src.database.models import DailyWorldProjection, Game, GameState
from src.game.daily_timeline import build_daily_timeline
from src.game.game_loop import GameLoop
from src.game.round.daily_choice_processor import DailyChoiceProcessor
from src.game.state import PlayerState
from src.game.world_projection_schema import compute_projection_source_hash
from src.services.daily_world_projection import DailyWorldProjectionService
from src.services.daily_world_projection_repository import (
    DailyWorldProjectionRepository,
)


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

    loop._reconcile_daily_world_projections({"_game_id": game_id})

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
