"""API-level degradation contracts for story music recommendations."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi.testclient import TestClient

from src.api.main import app
from src.services import music_service as music_service_module


class TimeoutMusicService:
    """Small real test service used to force the router down its degradation path."""

    async def analyze_story_for_music(
        self,
        story_text: str,
        character_settings: Optional[dict[str, Any]] = None,
        refresh: bool = False,
    ) -> Any:
        raise TimeoutError("upstream music recommendation timed out")

    async def get_song_play_url(self, song_id: int) -> Optional[str]:
        return None


def test_music_recommend_timeout_degrades_to_non_blocking_empty_recommendation() -> None:
    original_service = music_service_module._music_service
    music_service_module._music_service = TimeoutMusicService()  # type: ignore[assignment]
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/music/recommend",
                json={
                    "story_text": "顾晨曦在会议室整理用户数据，准备 AI 协作工具评审。",
                    "character_settings": {
                        "world_description": "2020年代中国互联网公司产品经理成长线"
                    },
                },
            )
    finally:
        music_service_module._music_service = original_service

    assert response.status_code == 200
    data = response.json()
    assert data["songs"] == []
    assert data["mood"] == "平静"
    assert data["scene_type"] == "叙事"
    assert "music_brief" in data
    assert "纯音乐" in data["keywords"]


class SlowMusicService:
    """Small real test service that would hang the route without a total timeout."""

    async def analyze_story_for_music(
        self,
        story_text: str,
        character_settings: Optional[dict[str, Any]] = None,
        refresh: bool = False,
    ) -> Any:
        await asyncio.sleep(1)
        raise AssertionError("route should enforce a short total timeout in this test")

    async def get_song_play_url(self, song_id: int) -> Optional[str]:
        return None


def test_music_recommend_long_upstream_call_uses_route_timeout_without_hanging() -> None:
    original_service = music_service_module._music_service
    music_service_module._music_service = SlowMusicService()  # type: ignore[assignment]
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/music/recommend",
                json={
                    "story_text": "产品经理在深夜复盘用户访谈，音乐推荐不应阻塞游戏。",
                },
            )
    finally:
        music_service_module._music_service = original_service

    assert response.status_code == 200
    assert response.json()["songs"] == []
