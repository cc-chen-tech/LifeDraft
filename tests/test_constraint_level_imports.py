"""导入验证测试：约束级别持久化相关模块可导入。"""


def test_update_game_settings_request_importable():
    from src.api.schemas import UpdateGameSettingsRequest

    req = UpdateGameSettingsRequest(constraint_level="master")
    assert req.constraint_level == "master"


def test_game_state_response_has_constraint_level():
    from src.api.schemas import GameStateResponse

    resp = GameStateResponse(
        game_id=1,
        player_state={},
        progress={},
        round_info={},
    )
    assert hasattr(resp, "constraint_level")
    assert resp.constraint_level == "expert"


def test_game_loop_has_quality_level_attribute():
    from src.game.game_loop import GameLoop

    loop = GameLoop(language="zh", quality_level="master")
    assert hasattr(loop, "quality_level")
    assert loop.quality_level == "master"
