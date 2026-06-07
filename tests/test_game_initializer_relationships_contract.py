"""Contracts for relationship settings accepted during game initialization."""

from unittest.mock import MagicMock

from src.game.game_initializer import GameInitializer


def test_initialize_game_normalizes_relationships_list_payload() -> None:
    """A frontend/API list-shaped relationships payload must not crash game creation."""
    db = MagicMock()
    db.create_game.return_value = 123
    initializer = GameInitializer(game_db=db, language="zh")

    game_loop, game_id = initializer.initialize_game_from_settings(
        character_settings={
            "narrative_style_id": "realistic_modern",
            "age": {"age": 22},
            "relationships": [
                {"name": "陆昊然", "relation": "导师", "description": "成熟的产品负责人"},
                {"name": "陈晓雨", "relation": "同学", "description": "数据分析师"},
                {"name": "", "relation": "空名应忽略"},
            ],
        },
        player_name="MiniMax生产验证",
        life_vision="成为可靠的产品经理",
        user_id=84,
    )

    assert game_id == 123
    state = game_loop.get_state()
    assert state is not None
    assert state.relationships["陆昊然"] == 50
    assert state.relationships["陈晓雨"] == 50

    saved_state = db.create_game.call_args.kwargs["initial_state"]
    saved_relationships = saved_state["character_settings"]["relationships"]
    assert isinstance(saved_relationships, dict)
    assert [person["name"] for person in saved_relationships["key_people"]] == [
        "陆昊然",
        "陈晓雨",
        "",
    ]
