"""Provider-free contracts for collection router identity and field handling."""

import pytest
from fastapi import HTTPException

from src.api.routers.collection import (
    _build_eligible_recognition_characters,
    _build_entity_recognition_history,
    _extract_named_entities_from_settings,
    _get_player_state,
    _require_user,
    generate_character_description,
    generate_item_description,
)
from src.api.services.session_service import session_service
from src.game.game_loop import GameLoop
from src.game.state import PlayerState

pytestmark = [pytest.mark.api]



def _session_loop(player_state: PlayerState) -> GameLoop:
    game_loop = GameLoop(language="zh")
    game_loop.player_state = player_state
    return game_loop


def test_collection_user_requirement_and_session_player_state_are_real() -> None:
    game_id = 782_001
    user_id = 762_001
    player_state = PlayerState(player_name="林岚", week=3, current_round=1)
    game_loop = _session_loop(player_state)
    session_service.put(game_id, game_loop, user_id=user_id, language="zh")

    try:
        session, restored_state = _get_player_state(game_id, user_id)

        assert _require_user(user_id) == user_id
        assert session.game_loop is game_loop
        assert restored_state is player_state
        with pytest.raises(HTTPException) as no_user:
            _require_user(None)
        with pytest.raises(HTTPException) as zero_user:
            _require_user(0)
        assert no_user.value.status_code == zero_user.value.status_code == 401
    finally:
        session_service.remove(game_id, user_id=user_id)


def test_structured_entity_names_normalize_legacy_and_explicit_shapes() -> None:
    explicit = _extract_named_entities_from_settings(
        [" 王明 ", {"person_name": "赵老师"}, {"character_name": "周姐"}, {"name": "王明"}]
    )
    mapping = _extract_named_entities_from_settings(
        {"甲同事": {}, "ignored": {"name": "乙同事"}}
    )

    assert explicit == ["王明", "赵老师", "周姐"]
    assert mapping == ["甲同事", "乙同事"]
    assert _extract_named_entities_from_settings("not-a-list") == []


def test_recognition_history_and_eligible_names_include_unfinished_current_story_once() -> None:
    player_state = PlayerState(
        player_name="林岚",
        week=4,
        current_round=2,
        character_settings={
            "relationships": [{"name": "导师"}, {"person_name": "编辑"}],
            "family": {"family_members": [{"character_name": "母亲"}]},
        },
        relationships={"编辑": 70, "同学": 40},
        round_history=[
            {
                "week": 3,
                "round": 1,
                "effects": {"relationships": {"同学": 2, "记者": 1}},
            }
        ],
        current_event_data={
            "story_text": "林岚在旧报刊中发现记者留下的批注。",
            "options": [{"effects": {"relationships": {"记者": 3, "馆长": 1}}}],
        },
        pending_storylines=[{"related_characters": ["馆长", "邻居"]}],
        foreshadowing_seeds=[{"related_characters": ["校友"]}],
        character_habits=[{"character": "编辑"}],
        character_arc_state={"实习生": {"phase": "arrival"}},
        world_breathing_events=[{"affected_npcs": ["记者", "司机"]}],
    )

    history = _build_entity_recognition_history(player_state)
    names = _build_eligible_recognition_characters(player_state)

    assert history[-1] == {
        "week": 4,
        "round": 2,
        "event_description": "林岚在旧报刊中发现记者留下的批注。",
    }
    assert names == ["导师", "编辑", "母亲", "同学", "记者", "馆长", "邻居", "校友", "实习生", "司机"]


@pytest.mark.asyncio
async def test_existing_description_commands_do_not_call_generation_providers() -> None:
    game_id = 782_002
    user_id = 762_002
    item_name = "旧 书"
    player_state = PlayerState(
        player_name="林岚",
        items={
            item_name: {
                "description": "这本旧书保存完整的社区迁徙记录，封面内页仍保留多位住户的详细批注、日期、借阅路线与管理员的长期核对说明。",
                "category": "document",
            }
        },
    )
    session_service.put(game_id, _session_loop(player_state), user_id=user_id, language="zh")

    try:
        character = await generate_character_description(game_id, "导师", user_id=user_id)
        item = await generate_item_description(game_id, "旧%20书", user_id=user_id)

        assert character.success is True
        assert character.message == "人物 导师 描述已存在"
        assert item.success is True
        assert item.message == "物品 旧 书 描述已存在"
    finally:
        session_service.remove(game_id, user_id=user_id)
