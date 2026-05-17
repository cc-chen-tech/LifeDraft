"""Collection recognition history tests."""

from types import SimpleNamespace


def test_entity_recognition_history_includes_current_unresolved_event() -> None:
    """智能识别应包含当前已展示但尚未选择的故事正文。"""
    from src.api.routers.collection import _build_entity_recognition_history

    player_state = SimpleNamespace(
        round_history=[],
        week=0,
        current_round=0,
        current_event_data={
            "event_description": "林见微在怀安书铺遇见赵崇古，柳成璧递来一本宋刊本。",
            "options": [{"text": "接受赵崇古的邀请"}],
        },
    )

    history = _build_entity_recognition_history(player_state)

    assert history == [
        {
            "week": 0,
            "round": 0,
            "event_description": "林见微在怀安书铺遇见赵崇古，柳成璧递来一本宋刊本。",
        }
    ]
