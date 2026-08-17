"""No-provider contracts for item and landmark extraction parsing."""

from src.services.item_extraction_service import ItemExtractionService
from src.services.landmark_extraction_service import LandmarkExtractionService
import pytest

pytestmark = [pytest.mark.unit]



def test_item_parser_keeps_new_items_and_normalizes_invalid_fields():
    items = ItemExtractionService(ai_client=None)._parse_extraction_response(
        '''{"items": [
            {"action": "new", "name": "旧钥匙", "description": "铜制钥匙", "category": "weapon", "importance": "critical", "acquired_context": "抽屉", "is_key_item": true},
            {"action": "new", "name": "未知物", "category": "invalid", "importance": "urgent"},
            {"action": "update", "name": "旧钥匙"},
            {"action": "new", "name": ""}
        ]}''',
        current_week=7,
    )

    assert [item.name for item in items] == ["旧钥匙", "未知物"]
    assert (items[0].category, items[0].importance, items[0].acquired_week) == (
        "weapon",
        "critical",
        7,
    )
    assert items[0].is_key_item is True
    assert (items[1].category, items[1].importance) == ("other", "normal")


def test_item_parser_rejects_malformed_or_missing_item_collections():
    service = ItemExtractionService(ai_client=None)

    assert service._parse_extraction_response("not json", current_week=1) == []
    assert service._parse_extraction_response('{"landmarks": []}', current_week=1) == []


def test_landmark_parser_creates_and_updates_only_known_landmarks():
    result = LandmarkExtractionService(ai_client=None)._parse_extraction_response(
        '''{"landmarks": [
            {"action": "new", "name": "河岸", "description": "雨后的河岸", "category": "nature", "importance": "important", "context": "会面", "is_key_location": true},
            {"action": "update", "name": "钟楼"},
            {"action": "update", "name": "不存在的地点"},
            {"action": "new", "name": "未知地点", "category": "invalid", "importance": "urgent"},
            {"action": "new", "name": ""}
        ]}''',
        current_week=4,
        existing_landmarks={"钟楼": {"name": "钟楼"}},
    )

    assert [entry["action"] for entry in result] == ["new", "update", "new"]
    riverbank = result[0]["landmark"]
    assert (riverbank.name, riverbank.category, riverbank.first_appear_week) == ("河岸", "nature", 4)
    assert result[1] == {"action": "update", "name": "钟楼"}
    assert (result[2]["landmark"].category, result[2]["landmark"].importance) == (
        "other",
        "normal",
    )


def test_landmark_parser_rejects_malformed_or_missing_landmark_collections():
    service = LandmarkExtractionService(ai_client=None)

    assert service._parse_extraction_response("not json", 1, {}) == []
    assert service._parse_extraction_response('{"items": []}', 1, {}) == []
