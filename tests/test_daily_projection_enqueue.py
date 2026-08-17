"""Accepted daily-event boundaries enqueue durable world projections."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event as sqlalchemy_event
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from config.feature_flags import reset_features, set_feature
from src.ai.models import EventOption, GameEvent
from src.database.models import Base, DailyWorldProjection, Game
from src.game.game_loop import GameLoop
from src.game.daily_timeline import build_daily_timeline
from src.game.state import PlayerState
from src.services.daily_world_projection import DailyWorldProjectionService

pytestmark = [pytest.mark.unit]



def _event(revision: int = 1) -> GameEvent:
    return GameEvent(
        event_id="day-0-projection",
        revision=revision,
        story_date="2026-08-17",
        event_description="孙悟空在东海边看见一艘搁浅的小船。",
        options=[
            EventOption(text="上船查看", effects={}),
            EventOption(text="沿海岸寻找船主", effects={}),
        ],
    )


def _state(event: GameEvent) -> PlayerState:
    return PlayerState(
        timeline=build_daily_timeline(start_date="2026-08-17", day_index=0),
        timeline_version=2,
        current_event_data=event.model_dump(),
    )


def test_replacement_enqueue_supersedes_old_projection_in_one_commit(db_engine) -> None:
    """Removing the replacement transaction would leave an older row runnable."""
    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        session.add(Game(game_id=156, initial_state={}))
        session.commit()

    service = DailyWorldProjectionService(session_factory=sessions)
    old = _event()
    state = _state(old)
    service.ensure_world_projection(156, old, state)

    replacement = _event(revision=2)
    service.ensure_replacement_world_projection(156, replacement, state)

    with sessions() as session:
        rows = (
            session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.revision)
            .all()
        )
        assert [(row.revision, row.status) for row in rows] == [
            (1, "superseded"),
            (2, "pending"),
        ]


def test_failed_ensure_commit_rolls_back_its_file_sqlite_row(tmp_path) -> None:
    """A nested savepoint must not commit a row before the outer transaction does."""

    engine = create_engine(f"sqlite:///{tmp_path / 'projection.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        session.add(Game(game_id=160, initial_state={}))
        session.commit()

    class CommitFailsSession(Session):
        def begin(self, **kwargs):
            transaction = super().begin(**kwargs)

            class CommitFailure:
                def __enter__(self):
                    return transaction.__enter__()

                def __exit__(self, *_args) -> None:
                    raise RuntimeError("injected commit failure")

            return CommitFailure()

    failing_sessions = sessionmaker(bind=engine, class_=CommitFailsSession)
    event = _event()
    with pytest.raises(RuntimeError, match="injected commit failure"):
        DailyWorldProjectionService(
            session_factory=failing_sessions
        ).ensure_world_projection(160, event, _state(event))

    with sessions() as observer:
        assert observer.query(DailyWorldProjection).count() == 0


def test_failed_replacement_rolls_back_new_revision_and_supersede_in_file_sqlite(
    tmp_path,
) -> None:
    """A replacement failure must leave neither a new row nor a fenced old row."""
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'replacement.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        session.add(Game(game_id=161, initial_state={}))
        session.commit()

    class SupersedeFailsRepository(DailyWorldProjectionRepository):
        def supersede(self, game_id: int, event_id: str, before_revision: int) -> int:
            super().supersede(game_id, event_id, before_revision)
            raise RuntimeError("injected supersede failure")

    old = _event()
    state = _state(old)
    service = DailyWorldProjectionService(session_factory=sessions)
    service.ensure_world_projection(161, old, state)
    with pytest.raises(RuntimeError, match="injected supersede failure"):
        DailyWorldProjectionService(
            session_factory=sessions,
            repository_factory=SupersedeFailsRepository,
        ).ensure_replacement_world_projection(161, _event(revision=2), state)

    with sessions() as observer:
        rows = observer.query(DailyWorldProjection).all()
        assert [(row.revision, row.status) for row in rows] == [(1, "pending")]


def test_late_replacement_revision_is_superseded_without_reopening_newer_work(
    tmp_path,
) -> None:
    """A delayed rev2 enqueue must not undo the accepted rev3 lifecycle."""
    engine = create_engine(f"sqlite:///{tmp_path / 'ordering.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        session.add(Game(game_id=162, initial_state={}))
        session.commit()

    service = DailyWorldProjectionService(session_factory=sessions)
    state = _state(_event())
    service.ensure_world_projection(162, _event(), state)
    service.ensure_replacement_world_projection(162, _event(revision=3), state)
    service.ensure_replacement_world_projection(162, _event(revision=2), state)

    with sessions() as observer:
        rows = (
            observer.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.revision)
            .all()
        )
        assert [(row.revision, row.status) for row in rows] == [
            (1, "superseded"),
            (2, "superseded"),
            (3, "pending"),
        ]


def test_replacement_serializes_callbacks_with_a_game_lock(tmp_path) -> None:
    """Without the per-game lock, concurrent revisions can both observe no newer row."""
    engine = create_engine(f"sqlite:///{tmp_path / 'locking.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        session.add(Game(game_id=164, initial_state={}))
        session.commit()

    statements = []

    def capture_game_lock(_connection, _cursor, statement, _parameters, *_args):
        if "UPDATE games" in statement:
            statements.append(statement)

    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_game_lock)
    try:
        service = DailyWorldProjectionService(session_factory=sessions)
        state = _state(_event())
        service.ensure_world_projection(164, _event(), state)
        service.ensure_replacement_world_projection(164, _event(revision=2), state)
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_game_lock)

    assert statements


def test_failed_normal_persistence_does_not_enqueue_projection(
    db_engine, monkeypatch
) -> None:
    """Treating a swallowed save failure as success would create a phantom job."""
    from src.api.routers.gameplay import sse_helpers

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        session.add(Game(game_id=156, initial_state={}))
        session.commit()
    service = DailyWorldProjectionService(session_factory=sessions)
    event = _event()
    state = _state(event)
    loop = SimpleNamespace(
        player_state=state,
        generate_round_event=lambda **_kwargs: event,
        get_state=lambda: state,
    )
    operation = SimpleNamespace(
        key=SimpleNamespace(resolved_mode="generate_missing"),
        operation_id="normal-save-fails",
        publish_story=lambda _chunk: None,
        publish_phase=lambda _phase: None,
        complete=lambda _event: None,
        fail=lambda *_args, **_kwargs: None,
    )

    monkeypatch.setattr(
        sse_helpers,
        "get_db",
        lambda: SimpleNamespace(save_game_progress=lambda *_: False),
    )
    monkeypatch.setattr(
        "src.services.daily_world_projection.get_daily_world_projection_service",
        lambda: service,
    )
    monkeypatch.setattr(
        "src.services.daily_recommended_prefetch.ensure_daily_recommended_prefetch",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        sse_helpers,
        "_trigger_round_illustration_generation",
        lambda *_args, **_kwargs: None,
    )

    sse_helpers._run_event_generation_operation(
        operation, loop, 156, SimpleNamespace(user_id=None)
    )

    with sessions() as session:
        assert session.query(DailyWorldProjection).count() == 0


def test_successful_normal_persistence_enqueues_projection_once(
    db_engine, monkeypatch
) -> None:
    """Skipping the post-save enqueue would leave an accepted story without work."""
    from src.api.routers.gameplay import sse_helpers

    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        session.add(Game(game_id=157, initial_state={}))
        session.commit()
    service = DailyWorldProjectionService(session_factory=sessions)
    event = _event()
    state = _state(event)
    loop = SimpleNamespace(
        player_state=state,
        generate_round_event=lambda **_kwargs: event,
        get_state=lambda: state,
    )
    operation = SimpleNamespace(
        key=SimpleNamespace(resolved_mode="generate_missing"),
        operation_id="normal-save-succeeds",
        publish_story=lambda _chunk: None,
        publish_phase=lambda _phase: None,
        complete=lambda _event: None,
        fail=lambda *_args, **_kwargs: None,
    )

    monkeypatch.setattr(
        sse_helpers,
        "get_db",
        lambda: SimpleNamespace(save_game_progress=lambda *_: True),
    )
    monkeypatch.setattr(
        "src.services.daily_world_projection.get_daily_world_projection_service",
        lambda: service,
    )
    monkeypatch.setattr(
        "src.services.daily_recommended_prefetch.ensure_daily_recommended_prefetch",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        sse_helpers,
        "_trigger_round_illustration_generation",
        lambda *_args, **_kwargs: None,
    )

    sse_helpers._run_event_generation_operation(
        operation, loop, 157, SimpleNamespace(user_id=None)
    )
    sse_helpers._run_event_generation_operation(
        operation, loop, 157, SimpleNamespace(user_id=None)
    )

    with sessions() as session:
        assert session.query(DailyWorldProjection).count() == 1


def test_daily_load_reconciles_current_and_explicit_pending_events_only(
    db_engine, monkeypatch
) -> None:
    """A broad history scan would silently enqueue legacy records on every load."""
    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        session.add(Game(game_id=159, initial_state={}))
        session.commit()
    service = DailyWorldProjectionService(session_factory=sessions)
    current = _event()
    state = _state(current)
    state.day_history = [
        {
            "event_id": "day-7-explicit-pending",
            "revision": 1,
            "day_index": 7,
            "story_date": "2026-08-24",
            "event_description": "一封未署名的信被塞进书店门缝。",
            "options": [
                {"text": "拆开信", "effects": {}},
                {"text": "先收起来", "effects": {}},
            ],
            "world_projection_status": "pending",
        },
        {
            "event_id": "legacy-complete",
            "revision": 1,
            "day_index": 0,
            "story_date": "2026-08-17",
            "event_description": "旧日记录不应在 PR2 被全量回填。",
            "options": [
                {"text": "继续", "effects": {}},
                {"text": "停下", "effects": {}},
            ],
            "world_projection_status": "complete",
        },
        {
            "event_id": "malformed-pending",
            "revision": 1,
            "day_index": 8,
            "story_date": "2026-08-25",
            "event_description": "",
            "options": [
                {"text": "继续", "effects": {}},
                {"text": "停下", "effects": {}},
            ],
            "world_projection_status": "pending",
        },
    ]
    state_dict = state.to_dict()
    state_dict["_game_id"] = 159
    monkeypatch.setattr(
        "src.services.daily_world_projection.get_daily_world_projection_service",
        lambda: service,
    )

    set_feature("daily_world_projection_v1", True)
    try:
        loop = GameLoop(language="zh")
        loop.load_game(state_dict)
        loop.load_game(state_dict)
    finally:
        reset_features()

    with sessions() as session:
        rows = (
            session.query(DailyWorldProjection)
            .order_by(DailyWorldProjection.event_id)
            .all()
        )
        assert [(row.event_id, row.day_index, row.story_date) for row in rows] == [
            ("day-0-projection", 0, "2026-08-17"),
            ("day-7-explicit-pending", 7, "2026-08-24"),
        ]


def test_daily_load_reconciles_complete_evt_current_event(
    db_engine, monkeypatch
) -> None:
    """A valid persisted event ID must not be rejected by an ID-prefix heuristic."""
    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        session.add(Game(game_id=165, initial_state={}))
        session.commit()
    service = DailyWorldProjectionService(session_factory=sessions)
    current = _event()
    current.event_id = "evt_5b4bc324"
    state_dict = _state(current).to_dict()
    state_dict["_game_id"] = 165
    monkeypatch.setattr(
        "src.services.daily_world_projection.get_daily_world_projection_service",
        lambda: service,
    )

    set_feature("daily_world_projection_v1", True)
    try:
        GameLoop(language="zh").load_game(state_dict)
    finally:
        reset_features()

    with sessions() as observer:
        assert [row.event_id for row in observer.query(DailyWorldProjection).all()] == [
            "evt_5b4bc324"
        ]


def test_daily_load_does_not_enqueue_current_event_with_generated_placeholder_id(
    db_engine, monkeypatch
) -> None:
    """A missing persisted ID must not become accepted through GameEvent defaults."""
    sessions = sessionmaker(bind=db_engine)
    with sessions() as session:
        session.add(Game(game_id=166, initial_state={}))
        session.commit()
    service = DailyWorldProjectionService(session_factory=sessions)
    current = _event()
    state = _state(current)
    state.current_event_data.pop("event_id")
    state_dict = state.to_dict()
    state_dict["_game_id"] = 166
    monkeypatch.setattr(
        "src.services.daily_world_projection.get_daily_world_projection_service",
        lambda: service,
    )

    set_feature("daily_world_projection_v1", True)
    try:
        GameLoop(language="zh").load_game(state_dict)
    finally:
        reset_features()

    with sessions() as observer:
        assert observer.query(DailyWorldProjection).count() == 0
