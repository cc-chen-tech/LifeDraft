"""Regression contracts from live story101 gameplay recovery testing."""

from __future__ import annotations

import pytest

from config.prompts.character_prompts import get_opening_story_prompt
from src.services.entity_recognition_service import EntityRecognitionService
from src.services.music_service import NeteaseMusicClient


class _FakeAIClient:
    def __init__(self, response: str) -> None:
        self.response = response

    def call(self, **_: object) -> str:
        return self.response


def test_entity_recognition_characters_are_gated_by_relationship_metadata() -> None:
    """Text fragments like 水门就/魏家 must not become characters without metadata."""
    service = EntityRecognitionService(
        _FakeAIClient(
            """
            {
              "items": [],
              "characters": [
                {"name": "陆子衿", "description": "情报提供者", "role": "线人", "importance": "important", "appear_count": 5, "appear_contexts": ["陆子衿递来纸条"]},
                {"name": "水门就", "description": "误切文本", "role": "故事人物", "importance": "normal", "appear_count": 1, "appear_contexts": ["水门就是..."]},
                {"name": "魏家", "description": "家族名", "role": "故事人物", "importance": "normal", "appear_count": 3, "appear_contexts": ["魏家商号"]}
              ],
              "landmarks": []
            }
            """
        )
    )

    result = service.recognize_from_history(
        round_history=[
            {
                "week": 1,
                "round": 0,
                "event_description": "陆子衿与叶闻溪建立线人关系。水门就是她们约定的暗号，魏家商号只是地点线索。",
            }
        ],
        existing_items=[],
        existing_characters=["叶闻溪"],
        existing_landmarks=[],
        min_appearances=1,
        language="zh",
        eligible_character_names=["陆子衿"],
    )

    assert [character["name"] for character in result["characters"]] == ["陆子衿"]


def test_entity_recognition_does_not_repropose_existing_eligible_character() -> None:
    """Already collected relationship characters should not return as new candidates."""
    service = EntityRecognitionService(
        _FakeAIClient(
            """
            {
              "items": [],
              "characters": [
                {"name": "陆子衿", "description": "情报提供者", "role": "线人", "importance": "important", "appear_count": 5, "appear_contexts": ["陆子衿递来纸条"]}
              ],
              "landmarks": []
            }
            """
        )
    )

    result = service.recognize_from_history(
        round_history=[{"event_description": "陆子衿再次出现，提醒叶闻溪不要走官道。"}],
        existing_items=[],
        existing_characters=["叶闻溪", "陆子衿"],
        existing_landmarks=[],
        min_appearances=1,
        language="zh",
        eligible_character_names=["陆子衿"],
    )

    assert result["characters"] == []


def test_opening_prompt_marks_life_vision_as_non_drifting_constraint() -> None:
    """A specific career/premise cannot be softened into an unrelated heritage story."""
    prompt = get_opening_story_prompt(
        character_settings={
            "era": {
                "era_description": "近未来城市新沪，由超级AI天枢管理",
                "year": 2024,
                "world_context": "科技巨头启明集团垄断公共数据",
            },
            "age": {"age": 33},
            "gender": {"gender": "女"},
            "world": {
                "world_description": "算法监控、数据黑市、科技公司黑幕",
                "social_system": "技术官僚与资本联盟治理",
                "technology_level": "人工智能、脑机接口、物联网高度成熟",
            },
        },
        player_name="叶闻溪",
        life_vision="近未来城市，女主是调查记者，揭露科技公司和城市系统的黑幕，第三人称叙事。",
        formatted_family_members="",
        language="zh",
    )

    assert "人生愿景硬约束" in prompt
    assert "调查记者" in prompt
    assert "科技公司" in prompt
    assert "不得改写为无关的遗产、非遗、中医传承、古代探案或武侠押镖主线" in prompt


@pytest.mark.asyncio
async def test_music_client_normalizes_http_media_url_to_https() -> None:
    """Production HTTPS pages must not receive raw http:// audio URLs."""

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"code": 200, "data": [{"url": "http://m7.music.126.net/song.mp3"}]}

    class _Client:
        async def get(self, *_: object, **__: object) -> _Response:
            return _Response()

    client = NeteaseMusicClient(base_url="http://music-api:3001")
    client.client = _Client()  # type: ignore[assignment]

    assert await client.get_song_url(123) == "https://m7.music.126.net/song.mp3"
