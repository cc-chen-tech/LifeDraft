"""Provider-free contracts for opening-story cache and SSE replay."""

import json
import time

import pytest
from fastapi import HTTPException

from src.api.routers.character import (
    _cache_lock,
    _opening_story_appears_truncated,
    _opening_story_cache,
    generate_opening_story,
)
from src.api.schemas import OpeningStoryRequest


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
    with _cache_lock:
        _opening_story_cache[player_name] = {
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
            _opening_story_cache.pop(player_name, None)


@pytest.mark.asyncio
async def test_fresh_inflight_opening_story_rejects_duplicate_request() -> None:
    player_name = "重复开场契约"
    with _cache_lock:
        _opening_story_cache[player_name] = {
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
            _opening_story_cache.pop(player_name, None)


def test_opening_story_truncation_handles_explicit_and_trivial_states() -> None:
    assert _opening_story_appears_truncated("", None, "zh") is False
    assert _opening_story_appears_truncated("很短的故事", None, "zh") is False
    assert _opening_story_appears_truncated("A short English story", None, "en") is False
    assert _opening_story_appears_truncated("任何长度的故事", "length", "zh") is True
