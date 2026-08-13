"""Real database contracts for saved-game and in-memory session recovery."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.api.services.session_service import SessionService
from src.database.models import Game, GameState, SessionLocal, User, init_db
from src.database.state_repository import StateRepository
from src.game.state import PlayerState


def _state(*, player_name: str, life_vision: str, week: int, round_number: int) -> dict:
    state = PlayerState(
        player_name=player_name,
        life_vision=life_vision,
        age=29,
        week=week,
        current_round=round_number,
        energy=72,
        mood=61,
        knowledge=43,
        wealth=50_000,
    ).to_dict()
    state["story_history"] = [f"第 {week} 周第 {round_number} 轮的持久化故事"]
    state["round_history"] = [
        {"week": week, "round": round_number, "choice": "保留最新快照"}
    ]
    return state


def test_session_recovery_uses_latest_owned_snapshot_and_legacy_identity_fields() -> None:
    init_db()
    suffix = uuid4().hex[:12]
    db = SessionLocal()
    service = SessionService()
    game_id: int | None = None
    owner_id: int | None = None
    intruder_id: int | None = None
    try:
        owner = User(
            private_id=f"session-owner-{suffix}",
            public_id=f"OWN{suffix[:7]}",
            display_name="Session Owner",
        )
        intruder = User(
            private_id=f"session-intruder-{suffix}",
            public_id=f"INT{suffix[:7]}",
            display_name="Session Intruder",
        )
        db.add_all([owner, intruder])
        db.flush()
        owner_id = int(owner.user_id)
        intruder_id = int(intruder.user_id)

        initial_state = _state(
            player_name="林舟", life_vision="守住旧城区的家业", week=1, round_number=0
        )
        game = Game(
            user_id=owner_id,
            language="zh",
            initial_state=initial_state,
            narrative_style_id="gothic_romance",
            constraint_level="expert",
        )
        db.add(game)
        db.flush()
        game_id = int(game.game_id)

        old_snapshot = _state(
            player_name="旧名字", life_vision="旧目标", week=2, round_number=1
        )
        latest_snapshot = _state(
            player_name="", life_vision="", week=5, round_number=2
        )
        # Simulate a legacy snapshot that lacked identity fields but retained progress.
        latest_snapshot.pop("player_name")
        latest_snapshot.pop("life_vision")
        db.add(
            GameState(
                game_id=game_id,
                week=2,
                age=29,
                state_json=old_snapshot,
                created_at=datetime.utcnow() - timedelta(minutes=2),
            )
        )
        db.add(
            GameState(
                game_id=game_id,
                week=5,
                age=29,
                state_json=latest_snapshot,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()

        loaded = StateRepository().load_saved_game(game_id, owner_id)

        assert loaded is not None
        assert loaded["_game_id"] == game_id
        assert loaded["week"] == 5
        assert loaded["current_round"] == 2
        assert loaded["round_history"] == [{"week": 5, "round": 2, "choice": "保留最新快照"}]
        assert loaded["player_name"] == "林舟"
        assert loaded["life_vision"] == "守住旧城区的家业"
        assert loaded["narrative_style_id"] == "gothic_romance"
        assert loaded["constraint_level"] == "expert"
        assert StateRepository().load_saved_game(game_id, intruder_id) is None

        restored = service.get_or_restore(game_id, owner_id)

        assert restored.user_id == owner_id
        assert restored.game_id == game_id
        assert restored.game_loop.player_state.week == 5
        assert restored.game_loop.player_state.current_round == 2
        assert restored.game_loop.player_state.player_name == "林舟"
        assert service.get(game_id, owner_id) is restored
        assert service.remove(game_id, owner_id) is True
        assert service.get(game_id, owner_id) is None

        with pytest.raises(HTTPException) as error:
            service.get_or_restore(game_id, intruder_id)
        assert error.value.status_code == 404
    finally:
        if game_id is not None and owner_id is not None:
            service.remove(game_id, owner_id)
        db.rollback()
        if game_id is not None:
            db.query(GameState).filter(GameState.game_id == game_id).delete()
            db.query(Game).filter(Game.game_id == game_id).delete()
        if owner_id is not None:
            db.query(User).filter(User.user_id == owner_id).delete()
        if intruder_id is not None:
            db.query(User).filter(User.user_id == intruder_id).delete()
        db.commit()
        db.close()
