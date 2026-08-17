"""Real database contracts for persisted games-router state."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.routers.games import (
    UpdateNarrativeStyleRequest,
    _deep_merge_dicts,
    _is_before_first_played_round,
    _mark_orphaned_generation_interrupted,
    delete_game,
    get_narrative_style,
    list_games,
    list_narrative_style_options,
    update_character_settings,
    update_narrative_style,
)
from src.api.schemas import UpdateCharacterSettingsRequest
from src.api.session_store import session_store
from src.database.models import Game, GameState, SessionLocal, User, init_db
from src.game.state import PlayerState

pytestmark = [pytest.mark.integration]



def _create_owned_game() -> tuple[int, int]:
    init_db()
    db = SessionLocal()
    try:
        prior_user = db.query(User).filter(User.private_id == "games-router-contract-owner").first()
        if prior_user:
            db.delete(prior_user)
            db.commit()

        owner = User(
            private_id="games-router-contract-owner",
            public_id="gamedb71",
            display_name="Games Contract Owner",
        )
        db.add(owner)
        db.flush()
        state = {
            "player_name": "沈若澜",
            "life_vision": "在深圳创办教育产品",
            "age": 32,
            "week": 0,
            "current_round": 0,
            "wealth": 12000,
            "character_settings": {
                "era": {"era_name": "2026年深圳"},
                "relationships": {"key_people": [{"name": "陆昊然", "role": "导师"}]},
            },
        }
        game = Game(user_id=owner.user_id, language="zh", initial_state=state)
        db.add(game)
        db.flush()
        db.add(GameState(game_id=game.game_id, week=0, age=32, state_json=state))
        db.commit()
        return int(owner.user_id), int(game.game_id)
    finally:
        db.close()


def _remove_owned_game(user_id: int, game_id: int) -> None:
    session_store.remove(game_id, user_id)
    db = SessionLocal()
    try:
        game = db.query(Game).filter(Game.game_id == game_id).first()
        if game:
            db.delete(game)
        owner = db.query(User).filter(User.user_id == user_id).first()
        if owner:
            db.delete(owner)
        db.commit()
    finally:
        db.close()


def test_games_helpers_preserve_nested_fields_and_interrupt_orphaned_generation() -> None:
    assert _deep_merge_dicts(
        {"era": {"name": "深圳", "year": 2026}, "wealth": {"amount": 12000}},
        {"era": {"name": "杭州"}, "wealth": {"currency": "CNY"}},
    ) == {
        "era": {"name": "杭州", "year": 2026},
        "wealth": {"amount": 12000, "currency": "CNY"},
    }
    assert _is_before_first_played_round({"week": 0, "current_round": 0}) is True
    assert _is_before_first_played_round({"week": 0, "current_round": 1}) is False

    state = PlayerState(resume_view={"phase": "generating", "operation": "opening-story"})
    _mark_orphaned_generation_interrupted(SimpleNamespace(get_state=lambda: state))

    assert state.resume_view == {
        "phase": "failed",
        "operation": "opening-story",
        "error": "上次生成会话已中断，请点击恢复当前进度后重试。",
    }


@pytest.mark.asyncio
async def test_owned_game_list_and_delete_use_real_database_records() -> None:
    user_id, game_id = _create_owned_game()
    try:
        listed = await list_games(user_id=user_id)
        item = next(item for item in listed if item.game_id == game_id)
        assert item.player_name == "沈若澜"
        assert item.week == 0
        assert item.age == 32
        assert item.has_progress is True

        deleted = await delete_game(game_id=game_id, user_id=user_id)
        assert deleted.message == "Game deleted"
        assert all(item.game_id != game_id for item in await list_games(user_id=user_id))
    finally:
        _remove_owned_game(user_id, game_id)


@pytest.mark.asyncio
async def test_preplay_character_settings_merge_strips_legacy_wealth() -> None:
    user_id, game_id = _create_owned_game()
    try:
        response = await update_character_settings(
            game_id=game_id,
            user_id=user_id,
            req=UpdateCharacterSettingsRequest(
                player_name="  林知夏  ",
                life_vision="在杭州做可持续教育",
                character_settings={
                    "relationships": {"key_people": [{"name": "陈晓雨", "role": "同事"}]},
                    "wealth": {"starting_wealth": 68000},
                },
            ),
        )

        assert response.success is True
        db = SessionLocal()
        try:
            saved = (
                db.query(GameState)
                .filter(GameState.game_id == game_id)
                .order_by(GameState.state_id.desc())
                .first()
            )
            assert saved is not None
            assert saved.state_json["player_name"] == "林知夏"
            assert saved.state_json["life_vision"] == "在杭州做可持续教育"
            assert "wealth" not in saved.state_json
            assert "wealth" not in saved.state_json["character_settings"]
            assert saved.state_json["character_settings"]["era"]["era_name"] == "2026年深圳"
            assert saved.state_json["character_settings"]["relationships"]["key_people"] == [
                {"name": "陈晓雨", "role": "同事"}
            ]
        finally:
            db.close()
    finally:
        _remove_owned_game(user_id, game_id)


@pytest.mark.asyncio
async def test_narrative_style_read_write_and_reject_unknown_style() -> None:
    user_id, game_id = _create_owned_game()
    try:
        options = await list_narrative_style_options(game_id=game_id, user_id=user_id)
        known_style = next(option for option in options if option.style_id == "chinese_classic_saga")

        initial = await get_narrative_style(game_id=game_id, user_id=user_id)
        assert initial.style_id == "chinese_classic_saga"

        updated = await update_narrative_style(
            game_id=game_id,
            user_id=user_id,
            req=UpdateNarrativeStyleRequest(style_id=known_style.style_id),
        )
        restored = await get_narrative_style(game_id=game_id, user_id=user_id)
        assert updated.success is True
        assert restored.style_id == known_style.style_id
        assert restored.style_name == known_style.style_name

        with pytest.raises(HTTPException, match="Unknown style_id") as exc_info:
            await update_narrative_style(
                game_id=game_id,
                user_id=user_id,
                req=UpdateNarrativeStyleRequest(style_id="unknown-style"),
            )
        assert exc_info.value.status_code == 400
    finally:
        _remove_owned_game(user_id, game_id)
