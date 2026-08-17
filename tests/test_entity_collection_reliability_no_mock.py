"""No-mock contracts for reliable entity recognition and add feedback."""

from pathlib import Path

from src.services.entity_recognition_service import EntityRecognitionService
import pytest

pytestmark = [pytest.mark.unit]



def _service() -> EntityRecognitionService:
    return EntityRecognitionService(None)


def test_clear_story_people_are_not_hidden_by_stale_metadata() -> None:
    story = (
        "沈建国先核对了病历。陈远走进办公室，把审计材料交给沈砚秋。"
        "周丽随后打来电话，提醒沈砚秋保留原始邮件。"
    )

    result = _service()._supplement_with_story_entities(
        result={"items": [], "characters": [], "landmarks": []},
        story_text=story,
        existing_items=[],
        existing_characters=["沈砚秋", "沈建国"],
        existing_landmarks=[],
        min_appearances=1,
        eligible_character_names=["沈建国"],
    )

    assert [character["name"] for character in result["characters"]] == ["陈远", "周丽"]


def test_ambiguous_phrases_remain_excluded_without_person_syntax() -> None:
    story = "水门就是双方约定的暗号，魏家商号只是地点线索。"

    result = _service()._supplement_with_story_entities(
        result={"items": [], "characters": [], "landmarks": []},
        story_text=story,
        existing_items=[],
        existing_characters=[],
        existing_landmarks=[],
        min_appearances=1,
        eligible_character_names=["陆子衿"],
    )

    assert result["characters"] == []


def test_first_context_starts_and_ends_on_sentence_boundaries() -> None:
    story = (
        "上海清晨的天空仍然灰蒙蒙，窗外高架上的车流已经排成缓慢的长线。"
        "陈远走进会议室，把完整的审计材料放在沈砚秋面前。"
        "周丽在门外等待。"
    )

    context = _service()._first_context("陈远", story)

    assert context == "陈远走进会议室，把完整的审计材料放在沈砚秋面前。"
    assert "陈远" in context


def test_frontend_add_completion_does_not_await_detail_refresh() -> None:
    store_source = Path("frontend/src/stores/useCollectionStore.ts").read_text(encoding="utf-8")
    action = store_source.split("addRecognizedEntities: async", 1)[1].split(
        "autoCollectRecognizedEntities:", 1
    )[0]

    assert "await api.collection.addEntities" in action
    assert "await get().fetchCollection(gameId, true)" not in action
    assert "void get().fetchCollection(gameId, true)" in action
    assert action.index("isLoading: false") < action.index("void get().fetchCollection")


def test_add_response_fields_match_frontend_consumer() -> None:
    router_source = Path("src/api/routers/collection.py").read_text(encoding="utf-8")
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    expected_fields = ("added_items", "added_characters", "added_landmarks")

    for field in expected_fields:
        assert f'"{field}"' in router_source
        assert f"{field}: string[]" in api_source
