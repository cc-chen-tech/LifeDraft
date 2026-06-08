"""Real DB integration tests for 2026-06-08 live UX regressions."""

from src.database.db import GameDatabase
from src.game.game_initializer import GameInitializer


def _settings_with_required_people_and_yuan_wealth() -> dict:
    return {
        "era": {"era_description": "2026 年现代互联网职场"},
        "age": {"age": 24},
        "wealth": {
            "wealth": 50000,
            "currency": "¥",
            "currency_name": "元",
            "wealth_description": "个人储蓄和家庭支持合计五万元。",
        },
        "relationships": {
            "key_people": [
                {"name": "陆昊然", "role": "导师", "relationship_desc": "产品导师"},
                {"name": "陈晓雨", "role": "闺蜜", "relationship_desc": "大学好友"},
                {"name": "林一凡", "role": "同期", "relationship_desc": "同期产品经理"},
            ]
        },
    }


def test_game_create_save_read_preserves_required_people_and_configured_wealth() -> None:
    database = GameDatabase()
    initializer = GameInitializer(game_db=database, language="zh")

    game_loop, game_id = initializer.initialize_game_from_settings(
        character_settings=_settings_with_required_people_and_yuan_wealth(),
        player_name="测试小可",
        life_vision="成为可靠的产品经理",
    )
    database.save_game_progress(game_id, game_loop.player_state)

    loaded = database.load_game_state(game_id)

    assert loaded is not None
    assert loaded["wealth"] == 50000
    assert loaded["character_settings"]["wealth"]["currency"] == "¥"
    assert loaded["character_settings"]["wealth"]["currency_name"] == "元"
    names = [
        person["name"]
        for person in loaded["character_settings"]["relationships"]["key_people"]
    ]
    assert names == ["陆昊然", "陈晓雨", "林一凡"]
    assert loaded["relationships"]["陆昊然"] == 50
    assert loaded["relationships"]["陈晓雨"] == 50
    assert loaded["relationships"]["林一凡"] == 50
