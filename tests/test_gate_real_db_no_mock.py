"""No-mock real database integration tests for history and scene image persistence."""

from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.deps import create_token
from src.api.routers.images import get_round_scene_image
from src.database.models import (Base, Game, GamePlaylist, GameState, SceneImage,
                                 SessionLocal, User, engine, init_db)
from src.database.user_manager import UserManager


def _persist_completed_choice_state(
    session,
    *,
    user_id: int,
    suffix: str,
) -> int:
    state_json = {
        "player_name": f"Choice Sync {suffix}",
        "life_vision": "验证重复 choice-sync 不进入恢复循环",
        "age": 28,
        "week": 1,
        "current_round": 1,
        "rounds_per_week": 3,
        "energy": 75,
        "mood": 63,
        "knowledge": 42,
        "wealth": 50000,
        "relationships": {"陈思颖": 55},
        "characters": {},
        "decision_history": [],
        "story_history": [],
        "four_week_summaries": [],
        "yearly_summaries": [],
        "round_history": [
            {
                "week": 1,
                "round": 0,
                "event_description": "李诗涵在咖啡馆里摊开渠道资料。",
                "story_continuation": "你决定给陈思颖打电话确认明天的安排。",
                "summary": "你确认了创业推进的下一步。",
                "choice": "致电陈思颖确认明天安排",
                "effects": {"energy": -5, "mood": 3},
                "effects_requested": {"energy": -5, "mood": 3},
                "resource_warnings": [],
                "event_concluded": False,
            }
        ],
        "weekly_summaries": [],
        "pending_storylines": [],
        "established_facts": [],
        "foreshadowing_seeds": [],
        "character_habits": [],
        "pending_character_introductions": [],
        "character_settings": {
            "era": {"year": 2024, "era_description": "2024年中国现代都市"},
            "relationships": {"key_people": [{"name": "陈思颖", "role": "创业伙伴"}]},
        },
        "constraint_level": "expert",
    }
    game = Game(user_id=user_id, language="zh", initial_state=state_json)
    session.add(game)
    session.flush()
    session.add(
        GameState(
            game_id=game.game_id,
            week=1,
            age=28,
            state_json=state_json,
        )
    )
    session.commit()
    return int(game.game_id)


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


def test_saved_games_list_is_limited_to_authenticated_user_real_db(client: TestClient) -> None:
    init_db()
    os.environ.setdefault("JWT_SECRET", "saved-game-isolation-test-secret")
    suffix = uuid4().hex[:12]

    session = SessionLocal()
    created_game_ids: list[int] = []
    created_user_ids: list[int] = []
    try:
        user_a = User(
            private_id=f"save-list-a-{suffix}",
            public_id=f"A{suffix[:7]}",
            display_name=f"Save List A {suffix}",
        )
        user_b = User(
            private_id=f"save-list-b-{suffix}",
            public_id=f"B{suffix[:7]}",
            display_name=f"Save List B {suffix}",
        )
        session.add_all([user_a, user_b])
        session.flush()
        created_user_ids.extend([int(user_a.user_id), int(user_b.user_id)])

        own_game = Game(
            user_id=user_a.user_id,
            language="zh",
            initial_state={"player_name": f"Owner {suffix}", "week": 2, "age": 29},
        )
        other_game = Game(
            user_id=user_b.user_id,
            language="zh",
            initial_state={"player_name": f"Other {suffix}", "week": 9, "age": 41},
        )
        session.add_all([own_game, other_game])
        session.flush()
        created_game_ids.extend([int(own_game.game_id), int(other_game.game_id)])
        session.add_all(
            [
                GameState(
                    game_id=own_game.game_id,
                    week=2,
                    age=29,
                    state_json={"player_name": f"Owner Latest {suffix}", "week": 2, "age": 29},
                ),
                GameState(
                    game_id=other_game.game_id,
                    week=9,
                    age=41,
                    state_json={"player_name": f"Other Latest {suffix}", "week": 9, "age": 41},
                ),
            ]
        )
        session.commit()

        token = create_token(int(user_a.user_id))
        response = client.get("/api/games", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        payload = response.json()
        ids = {item["game_id"] for item in payload}
        names = {item["player_name"] for item in payload}

        assert int(own_game.game_id) in ids
        assert int(other_game.game_id) not in ids
        assert f"Owner Latest {suffix}" in names
        assert f"Other Latest {suffix}" not in names
    finally:
        session.rollback()
        if created_game_ids:
            session.query(GameState).filter(GameState.game_id.in_(created_game_ids)).delete(
                synchronize_session=False
            )
            session.query(Game).filter(Game.game_id.in_(created_game_ids)).delete(
                synchronize_session=False
            )
        if created_user_ids:
            session.query(User).filter(User.user_id.in_(created_user_ids)).delete(
                synchronize_session=False
            )
        session.commit()
        session.close()


def test_saved_game_load_rejects_other_users_game_real_db(client: TestClient) -> None:
    init_db()
    os.environ.setdefault("JWT_SECRET", "saved-game-isolation-test-secret")
    suffix = uuid4().hex[:12]

    session = SessionLocal()
    created_game_ids: list[int] = []
    created_user_ids: list[int] = []
    try:
        user_a = User(
            private_id=f"save-load-a-{suffix}",
            public_id=f"C{suffix[:7]}",
            display_name=f"Save Load A {suffix}",
        )
        user_b = User(
            private_id=f"save-load-b-{suffix}",
            public_id=f"D{suffix[:7]}",
            display_name=f"Save Load B {suffix}",
        )
        session.add_all([user_a, user_b])
        session.flush()
        created_user_ids.extend([int(user_a.user_id), int(user_b.user_id)])

        other_game = Game(
            user_id=user_b.user_id,
            language="zh",
            initial_state={"player_name": f"Forbidden {suffix}", "week": 5, "age": 37},
        )
        session.add(other_game)
        session.flush()
        created_game_ids.append(int(other_game.game_id))
        session.add(
            GameState(
                game_id=other_game.game_id,
                week=5,
                age=37,
                state_json={"player_name": f"Forbidden Latest {suffix}", "week": 5, "age": 37},
            )
        )
        session.commit()

        token = create_token(int(user_a.user_id))
        response = client.get(
            f"/api/games/{int(other_game.game_id)}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        assert f"Forbidden Latest {suffix}" not in response.text
    finally:
        session.rollback()
        if created_game_ids:
            session.query(GameState).filter(GameState.game_id.in_(created_game_ids)).delete(
                synchronize_session=False
            )
            session.query(Game).filter(Game.game_id.in_(created_game_ids)).delete(
                synchronize_session=False
            )
        if created_user_ids:
            session.query(User).filter(User.user_id.in_(created_user_ids)).delete(
                synchronize_session=False
            )
        session.commit()
        session.close()






def test_duplicate_choice_sync_returns_latest_saved_result_real_db(client: TestClient) -> None:
    init_db()
    os.environ.setdefault("JWT_SECRET", "choice-sync-idempotency-test-secret")
    suffix = uuid4().hex[:12]

    session = SessionLocal()
    created_game_ids: list[int] = []
    created_user_ids: list[int] = []
    try:
        user = User(
            private_id=f"choice-sync-{suffix}",
            public_id=f"E{suffix[:7]}",
            display_name=f"Choice Sync {suffix}",
        )
        session.add(user)
        session.flush()
        created_user_ids.append(int(user.user_id))
        game_id = _persist_completed_choice_state(
            session,
            user_id=int(user.user_id),
            suffix=suffix,
        )
        created_game_ids.append(game_id)

        token = create_token(int(user.user_id))
        response = client.post(
            f"/api/games/{game_id}/choice-sync",
            json={"option_index": 0},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "story_continuation": "你决定给陈思颖打电话确认明天的安排。",
            "summary": "你确认了创业推进的下一步。",
            "effects_applied": {"energy": -5, "mood": 3},
            "effects_requested": {"energy": -5, "mood": 3},
            "resource_warnings": [],
            "need_weekly_summary": False,
            "weekly_summary": None,
            "game_over": False,
        }
    finally:
        session.rollback()
        if created_game_ids:
            session.query(GameState).filter(GameState.game_id.in_(created_game_ids)).delete(
                synchronize_session=False
            )
            session.query(Game).filter(Game.game_id.in_(created_game_ids)).delete(
                synchronize_session=False
            )
        if created_user_ids:
            session.query(User).filter(User.user_id.in_(created_user_ids)).delete(
                synchronize_session=False
            )
        session.commit()
        session.close()


def test_duplicate_custom_choice_sync_returns_latest_saved_result_real_db(
    client: TestClient,
) -> None:
    init_db()
    os.environ.setdefault("JWT_SECRET", "choice-sync-idempotency-test-secret")
    suffix = uuid4().hex[:12]

    session = SessionLocal()
    created_game_ids: list[int] = []
    created_user_ids: list[int] = []
    try:
        user = User(
            private_id=f"custom-choice-sync-{suffix}",
            public_id=f"F{suffix[:7]}",
            display_name=f"Custom Choice Sync {suffix}",
        )
        session.add(user)
        session.flush()
        created_user_ids.append(int(user.user_id))
        game_id = _persist_completed_choice_state(
            session,
            user_id=int(user.user_id),
            suffix=suffix,
        )
        created_game_ids.append(game_id)

        token = create_token(int(user.user_id))
        response = client.post(
            f"/api/games/{game_id}/custom-choice-sync",
            json={"custom_text": "继续确认明天安排"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["story_continuation"] == "你决定给陈思颖打电话确认明天的安排。"
        assert payload["summary"] == "你确认了创业推进的下一步。"
        assert payload["effects_applied"] == {"energy": -5, "mood": 3}
        assert payload["effects_requested"] == {"energy": -5, "mood": 3}
        assert payload["need_weekly_summary"] is False
        assert payload["game_over"] is False
    finally:
        session.rollback()
        if created_game_ids:
            session.query(GameState).filter(GameState.game_id.in_(created_game_ids)).delete(
                synchronize_session=False
            )
            session.query(Game).filter(Game.game_id.in_(created_game_ids)).delete(
                synchronize_session=False
            )
        if created_user_ids:
            session.query(User).filter(User.user_id.in_(created_user_ids)).delete(
                synchronize_session=False
            )
        session.commit()
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
