"""Accepted daily-event boundaries enqueue durable world projections."""

from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker

from src.ai.models import EventOption, GameEvent
from src.database.models import DailyWorldProjection, Game
from src.game.game_loop import GameLoop
from src.game.daily_timeline import build_daily_timeline
from src.game.state import PlayerState
from src.services.daily_world_projection import DailyWorldProjectionService


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
            "event_id": "explicit-pending",
            "revision": 1,
            "day_index": 0,
            "story_date": "2026-08-17",
            "event_description": "一封未署名的信被塞进书店门缝。",
            "options": [{"text": "拆开信"}, {"text": "先收起来"}],
            "world_projection_status": "pending",
        },
        {
            "event_id": "legacy-complete",
            "revision": 1,
            "day_index": 0,
            "story_date": "2026-08-17",
            "event_description": "旧日记录不应在 PR2 被全量回填。",
            "options": [{"text": "继续"}, {"text": "停下"}],
            "world_projection_status": "complete",
        },
    ]
    state_dict = state.to_dict()
    state_dict["_game_id"] = 159
    monkeypatch.setattr(
        "src.services.daily_world_projection.get_daily_world_projection_service",
        lambda: service,
    )

    loop = GameLoop(language="zh")
    loop.load_game(state_dict)

    with sessions() as session:
        assert [row.event_id for row in session.query(DailyWorldProjection).all()] == [
            "day-0-projection",
            "explicit-pending",
        ]
