"""Provider-free contracts for opening-story cache and SSE replay."""

import json
import time

import pytest
from fastapi import HTTPException

from src.api.routers.character import (
    _build_opening_story_cache_key,
    _cache_lock,
    _opening_story_appears_truncated,
    _opening_story_cache,
    generate_opening_story,
)
from src.api.schemas import OpeningStoryRequest

pytestmark = [pytest.mark.unit]



def _request(player_name: str) -> OpeningStoryRequest:
    return OpeningStoryRequest(
        character_settings={"identity": {"name": player_name}},
        player_name=player_name,
        life_vision="建立一座社区图书馆",
        language="zh",
    )


@pytest.mark.asyncio
async def test_cached_opening_story_replays_complete_sse_contract() -> None:
    player_name = "缓存开场契约"
    story = "林岚推开图书馆的木门，决定先整理遗失多年的社区档案。"
    cache_key = _build_opening_story_cache_key(_request(player_name))
    with _cache_lock:
        _opening_story_cache[cache_key] = {
            "generating": False,
            "result": story,
            "timestamp": time.time(),
        }

    try:
        response = await generate_opening_story(_request(player_name))
        chunks = [chunk async for chunk in response.body_iterator]
        frames = [chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in chunks]

        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache"
        assert json.loads(frames[0].split("data: ", 1)[1]) == {"phase": "cached"}
        assert json.loads(frames[1].split("data: ", 1)[1]) == story
        assert json.loads(frames[2].split("data: ", 1)[1]) == {"full_story": story}
    finally:
        with _cache_lock:
            _opening_story_cache.pop(cache_key, None)


@pytest.mark.asyncio
async def test_fresh_inflight_opening_story_rejects_duplicate_request() -> None:
    player_name = "重复开场契约"
    cache_key = _build_opening_story_cache_key(_request(player_name))
    with _cache_lock:
        _opening_story_cache[cache_key] = {
            "generating": True,
            "result": None,
            "timestamp": time.time(),
        }

    try:
        with pytest.raises(HTTPException) as duplicate:
            await generate_opening_story(_request(player_name))

        assert duplicate.value.status_code == 409
        assert duplicate.value.detail == "Opening story generation in progress"
    finally:
        with _cache_lock:
            _opening_story_cache.pop(cache_key, None)


def test_opening_story_truncation_handles_explicit_and_trivial_states() -> None:
    assert _opening_story_appears_truncated("", None, "zh") is False
    assert _opening_story_appears_truncated("很短的故事", None, "zh") is False
    assert _opening_story_appears_truncated("A short English story", None, "en") is False
    assert _opening_story_appears_truncated("任何长度的故事", "length", "zh") is True


def test_opening_story_cache_key_isolates_same_name_different_settings() -> None:
    """P0-正确性：同名玩家但设定不同必须使用不同缓存 key。"""
    base = _request("张三")
    same = OpeningStoryRequest(
        character_settings={"identity": {"name": "张三"}},
        player_name="张三",
        life_vision="建立一座社区图书馆",
        language="zh",
    )
    different = OpeningStoryRequest(
        character_settings={"identity": {"name": "张三"}, "era": {"era_name": "古代"}},
        player_name="张三",
        life_vision="建立一座社区图书馆",
        language="zh",
    )
    assert _build_opening_story_cache_key(base) == _build_opening_story_cache_key(same)
    assert _build_opening_story_cache_key(base) != _build_opening_story_cache_key(different)


def test_opening_story_cache_prunes_expired_and_overflow_entries() -> None:
    """P3-内存：过期条目与超出上限的最旧条目被淘汰。"""
    from src.api.routers import character as char_module

    now = time.time()
    with _cache_lock:
        _opening_story_cache.clear()
        try:
            _opening_story_cache["expired"] = {
                "generating": False,
                "result": None,
                "timestamp": now - char_module.OPENING_STORY_CACHE_MAX_AGE - 1,
            }
            _opening_story_cache["fresh"] = {
                "generating": False,
                "result": "新",
                "timestamp": now,
            }
            char_module._prune_opening_story_cache_locked(now)
            assert "expired" not in _opening_story_cache
            assert "fresh" in _opening_story_cache
        finally:
            _opening_story_cache.clear()
