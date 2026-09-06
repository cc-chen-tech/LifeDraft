"""Regression tests for collection entity typing and daily materialization."""

from unittest.mock import MagicMock

import pytest

from src.game.state import PlayerState
from src.services.collection_service import CollectionService
from src.services.entity_recognition_service import EntityRecognitionService

pytestmark = pytest.mark.unit


class _FakeAIClient:
    def __init__(self, response: str) -> None:
        self.response = response

    def call(self, **_: object) -> str:
        return self.response


class _FailingAIClient:
    def call(self, **_: object) -> str:
        raise RuntimeError("temporary provider failure")


def test_recognition_keeps_mythic_items_and_landmarks_out_of_characters() -> None:
    """强语义物品/标志物不能因中文正则或 LLM 串类而变成人物。"""
    service = EntityRecognitionService(_FakeAIClient("""
            {
              "items": [],
              "characters": [
                {"name": "孙悟空", "description": "齐天大圣", "role": "故事人物"},
                {"name": "金箍棒", "description": "误分类物品", "role": "故事人物"},
                {"name": "花果山", "description": "误分类地点", "role": "故事人物"},
                {"name": "杨戬立", "description": "姓名后的动作片段", "role": "故事人物"},
                {"name": "金纹", "description": "兵器纹路", "role": "故事人物"},
                {"name": "阿翠照", "description": "姓名后的动作片段", "role": "故事人物"},
                {"name": "石下传", "description": "叙事片段", "role": "故事人物"}
              ],
              "landmarks": []
            }
            """))

    result = service.recognize_from_history(
        round_history=[
            {
                "event_description": (
                    "孙悟空在花果山取出金箍棒，杨戬握住金箍棒观察其金纹。"
                )
            }
        ],
        existing_items=[],
        existing_characters=["孙悟空", "杨戬", "阿翠"],
        existing_landmarks=[],
        min_appearances=1,
        language="zh",
    )

    character_names = {entity["name"] for entity in result["characters"]}
    item_names = {entity["name"] for entity in result["items"]}
    landmark_names = {entity["name"] for entity in result["landmarks"]}
    assert "孙悟空" in character_names
    assert {"金箍棒", "金纹"}.isdisjoint(character_names)
    assert "杨戬立" not in character_names
    assert "阿翠照" not in character_names
    assert "石下传" not in character_names
    assert "金箍棒" in item_names
    assert "花果山" in landmark_names


def test_recognition_uses_deterministic_fallback_when_ai_is_unavailable() -> None:
    """AI 不可用时，明确的物品和标志物也不能全部丢失。"""
    service = EntityRecognitionService(None)

    result = service.recognize_from_history(
        round_history=[
            {"event_description": "孙悟空在花果山握紧金箍棒，准备前往东海龙宫。"}
        ],
        existing_items=[],
        existing_characters=["孙悟空"],
        existing_landmarks=[],
        min_appearances=1,
        language="zh",
    )

    assert "金箍棒" in {entity["name"] for entity in result["items"]}
    assert {"花果山", "东海龙宫"}.issubset(
        {entity["name"] for entity in result["landmarks"]}
    )


def test_recognition_uses_deterministic_fallback_when_ai_call_fails() -> None:
    """LLM 单次故障不应让收藏识别整体变成空结果。"""
    service = EntityRecognitionService(_FailingAIClient())

    result = service.recognize_from_history(
        round_history=[{"event_description": "孙悟空在花果山取出金箍棒。"}],
        existing_items=[],
        existing_characters=["孙悟空"],
        existing_landmarks=[],
        min_appearances=1,
        language="zh",
    )

    assert [entity["name"] for entity in result["items"]] == ["金箍棒"]
    assert [entity["name"] for entity in result["landmarks"]] == ["花果山"]


def test_collection_write_path_rejects_cross_category_character_candidates() -> None:
    """即使客户端篡改识别响应，写入层也不能把物品写进人物表。"""
    state = PlayerState(player_name="唐三藏")
    service = CollectionService(MagicMock())

    result = service.add_entities(
        state,
        items=[],
        landmarks=[],
        characters=[
            {"name": "金箍棒", "description": "物品"},
            {"name": "孙悟空", "description": "人物"},
        ],
    )

    assert result["added_characters"] == ["孙悟空"]
    assert "金箍棒" not in state.characters


def test_daily_entity_materializer_is_idempotent_and_separates_types() -> None:
    """每日后处理应落入收藏，重试同一事件不能重复新增或串类。"""
    from src.services.entity_recognition_materializer import (
        materialize_recognized_entities,
    )

    state = PlayerState(player_name="唐三藏")
    entities = {
        "items": [{"name": "金箍棒", "description": "如意金箍棒"}],
        "characters": [
            {"name": "孙悟空", "description": "齐天大圣"},
            {"name": "花果山", "description": "错误人物"},
        ],
        "landmarks": [{"name": "花果山", "description": "猴王故乡"}],
    }

    first = materialize_recognized_entities(state, entities, source_event_id="day-1")
    second = materialize_recognized_entities(state, entities, source_event_id="day-1")

    assert first["added_items"] == ["金箍棒"]
    assert first["added_characters"] == ["孙悟空"]
    assert first["added_landmarks"] == ["花果山"]
    assert second["added_items"] == []
    assert second["added_characters"] == []
    assert second["added_landmarks"] == []
    assert set(state.items) == {"金箍棒"}
    assert set(state.characters) == {"孙悟空"}
    assert set(state.landmarks) == {"花果山"}


def test_daily_entity_materializer_rejects_ambiguous_unknown_names() -> None:
    """未知名称同时出现在多类结果中时，宁可不入库也不串类。"""
    from src.services.entity_recognition_materializer import (
        materialize_recognized_entities,
    )

    state = PlayerState(player_name="唐三藏")
    result = materialize_recognized_entities(
        state,
        {
            "items": [{"name": "玄铁令"}],
            "characters": [{"name": "玄铁令"}],
            "landmarks": [{"name": "玄铁令"}],
        },
    )

    assert result == {
        "added_items": [],
        "added_characters": [],
        "added_landmarks": [],
    }
    assert not state.items
    assert not state.characters
    assert not state.landmarks


def test_daily_entity_materializer_sanitizes_untrusted_numeric_fields() -> None:
    """异常 AI 数值不能让每日后处理整体失败。"""
    from src.services.entity_recognition_materializer import (
        materialize_recognized_entities,
    )

    state = PlayerState(player_name="唐三藏")
    result = materialize_recognized_entities(
        state,
        {
            "items": [],
            "characters": [{"name": "孙悟空", "affinity": "not-a-number"}],
            "landmarks": [{"name": "花果山", "appear_count": "not-a-number"}],
        },
    )

    assert result["added_characters"] == ["孙悟空"]
    assert result["added_landmarks"] == ["花果山"]
    assert state.characters["孙悟空"]["affinity"] == 50
    assert state.landmarks["花果山"]["appear_count"] == 1
