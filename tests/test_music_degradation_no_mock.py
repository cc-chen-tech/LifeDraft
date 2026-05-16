"""Regression tests for graceful music upstream degradation."""

from __future__ import annotations

import httpx
import pytest

from src.services.music_service import NeteaseMusicClient


class Always503Client:
    def __init__(self) -> None:
        self.calls = 0

    async def get(self, url: str, params: dict[str, int]) -> httpx.Response:
        self.calls += 1
        request = httpx.Request("GET", url, params=params)
        response = httpx.Response(503, request=request)
        raise httpx.HTTPStatusError("upstream unavailable", request=request, response=response)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_song_url_503_degrades_fast_without_retry_noise() -> None:
    music_client = NeteaseMusicClient(base_url="http://music.local")
    upstream = Always503Client()
    music_client.client = upstream  # type: ignore[assignment]

    url = await music_client.get_song_url(12345)

    assert url is None
    assert upstream.calls == 1
