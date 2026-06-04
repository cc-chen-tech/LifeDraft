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


def test_recognition_eligibility_includes_current_event_relationships_and_story_roles() -> None:
    """当前事件和剧情元数据中的人物应进入智能识别候选白名单。"""
    from src.api.routers.collection import _build_eligible_recognition_characters

    player_state = SimpleNamespace(
        player_name="李婉清",
        relationships={"陈一鸣": 55, "赵铭": 48},
        character_settings={
            "relationships": {
                "key_people": [{"name": "陈律师", "role": "法律顾问"}],
                "important_people": [{"name": "张副总", "relationship_desc": "公司高管"}],
            },
            "family": {"family_members": []},
        },
        current_event_data={
            "event_description": "刘洋递来审计材料，王亮说启明集团正在施压。",
            "options": [
                {"text": "联系周先生", "effects": {"relationships": {"周先生": 5}}},
            ],
        },
        round_history=[
            {
                "effects": {"relationships": {"刘洋": 3}},
            }
        ],
        pending_storylines=[
            {"description": "审计线推进", "related_characters": ["王亮"]},
        ],
        character_habits=[
            {"character": "周先生", "habit": "只在电话里透露线索"},
        ],
    )

    eligible = _build_eligible_recognition_characters(player_state)

    assert set(eligible) >= {"陈一鸣", "陈律师", "张副总", "赵铭", "刘洋", "周先生", "王亮"}
    assert "李婉清" not in eligible
    assert "启明集团" not in eligible
