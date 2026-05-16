"""No-mock real database integration tests for history and scene image persistence."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.api.routers.images import get_round_scene_image
from src.database.models import (Base, Game, GameState, SceneImage,
                                 SessionLocal, User, engine, init_db)
from src.database.user_manager import UserManager


def test_user_registration_recovers_when_previous_test_removed_schema() -> None:
    """E2E auth should recover if a destructive DB test dropped SQLite tables."""
    init_db()
    Base.metadata.drop_all(engine)

    manager = UserManager()
    try:
        user, private_id = manager.create_user("Recovered User")

        assert user.user_id is not None
        assert user.display_name == "Recovered User"
        assert private_id
    finally:
        manager.close()
        init_db()


def test_round_history_save_read_chain_uses_real_database() -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Gate User")
        session.add(user)
        session.flush()

        player_state = {
            "player_name": "陆明",
            "week": 4,
            "current_round": 2,
            "round_history": [
                {
                    "week": 4,
                    "round": 1,
                    "event_description": "旧案在雨夜重新浮出水面。",
                    "story_continuation": "他选择追查账册。",
                    "choice": "追查账册",
                }
            ],
            "current_event_data": {
                "event_description": "新一轮事件文本",
                "options": [{"text": "继续查证", "effects": {"knowledge": 5}}],
            },
        }
        game = Game(user_id=user.user_id, language="zh", initial_state=player_state)
        session.add(game)
        session.flush()

        snapshot = GameState(
            game_id=game.game_id,
            week=4,
            age=26,
            state_json=player_state,
        )
        session.add(snapshot)
        session.commit()

        loaded = session.query(GameState).filter(GameState.game_id == game.game_id).one()
        loaded_state = loaded.state_json

        assert loaded_state["round_history"][0]["week"] == 4
        assert loaded_state["round_history"][0]["round"] == 1
        assert loaded_state["current_event_data"]["options"][0]["text"] == "继续查证"
    finally:
        session.rollback()
        session.close()


def test_scene_image_save_read_chain_uses_week_round_stage_key() -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Scene User")
        session.add(user)
        session.flush()
        game = Game(user_id=user.user_id, language="zh", initial_state={"player_name": "陆明"})
        session.add(game)
        session.flush()

        scene = SceneImage(
            game_id=game.game_id,
            week=7,
            round_number=2,
            stage="event",
            scene_description="码头边的对峙",
            final_prompt="cinematic scene",
            storage_path="/tmp/story2-scene.png",
            storage_type="local",
            referenced_images=[11, 12],
            importance_score="high",
        )
        session.add(scene)
        other_stage = SceneImage(
            game_id=game.game_id,
            week=7,
            round_number=2,
            stage="result",
            scene_description="选择后的追逐",
            final_prompt="cinematic result scene",
            storage_path="/tmp/story2-scene-result.png",
            storage_type="local",
            referenced_images=[13],
            importance_score="normal",
        )
        other_round = SceneImage(
            game_id=game.game_id,
            week=7,
            round_number=3,
            stage="event",
            scene_description="次轮清晨",
            final_prompt="cinematic next scene",
            storage_path="/tmp/story2-scene-next.png",
            storage_type="local",
            referenced_images=[14],
            importance_score="normal",
        )
        session.add(other_stage)
        session.add(other_round)
        session.commit()

        loaded = (
            session.query(SceneImage)
            .filter(
                SceneImage.game_id == game.game_id,
                SceneImage.week == 7,
                SceneImage.round_number == 2,
                SceneImage.stage == "event",
            )
            .one()
        )

        assert loaded.scene_description == "码头边的对峙"
        assert loaded.referenced_images == [11, 12]
        assert loaded.storage_type == "local"
        assert loaded.stage == "event"
        assert loaded.round_number == 2
    finally:
        session.rollback()
        session.close()


@pytest.mark.asyncio
async def test_missing_scene_image_uses_latest_game_state_without_game_player_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_db()
    private_id = f"priv_{uuid4().hex[:16]}"
    public_id = f"pub_{uuid4().hex[:6]}"
    triggered: list[dict[str, object]] = []

    def capture_background_generation(**kwargs: object) -> None:
        triggered.append(kwargs)

    monkeypatch.setattr(
        "src.api.routers.images._trigger_scene_generation_in_background",
        capture_background_generation,
    )

    session = SessionLocal()
    try:
        user = User(private_id=private_id, public_id=public_id, display_name="Scene Missing")
        session.add(user)
        session.flush()

        state_json = {
            "player_name": "陆明",
            "week": 9,
            "current_event_data": {
                "event_description": "陆明站在雨后的码头，看见账册被塞进旧木箱。",
            },
            "character_settings": {
                "identity": {"name": "陆明"},
                "era": {"era_name": "近代"},
            },
        }
        game = Game(user_id=user.user_id, language="zh", initial_state={"player_name": "陆明"})
        session.add(game)
        session.flush()
        session.add(GameState(game_id=game.game_id, week=9, age=26, state_json=state_json))
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await get_round_scene_image(
                request=SimpleNamespace(cookies={}),
                game_id=int(game.game_id),
                round_number=2,
                week=9,
                stage="event",
                db=session,
                user=int(user.user_id),
            )

        assert exc_info.value.status_code == 202
        assert triggered == [
            {
                "game_id": int(game.game_id),
                "week": 9,
                "round_number": 2,
                "stage": "event",
                "story_text": "陆明站在雨后的码头，看见账册被塞进旧木箱。",
                "character_settings": state_json["character_settings"],
                "player_name": "陆明",
            }
        ]
    finally:
        session.rollback()
        session.close()
