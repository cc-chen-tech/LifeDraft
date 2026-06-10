"""Tests for NeteaseMusicClient (search / get_song_url)."""

from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.music_service import NeteaseMusicClient, Song

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(status_code: int, json_data: Optional[dict] = None) -> MagicMock:
    """Create a fake httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"{status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


SEARCH_OK_JSON = {
    "code": 200,
    "result": {
        "songs": [
            {
                "id": 1001,
                "name": "测试歌曲",
                "artists": [{"name": "歌手A"}],
                "album": {"name": "专辑X"},
                "duration": 240000,
            },
            {
                "id": 1002,
                "name": "第二首",
                "artists": [{"name": "歌手B"}, {"name": "歌手C"}],
                "album": {"name": "专辑Y"},
                "duration": 180000,
            },
        ]
    },
}

SONG_URL_OK_JSON = {
    "code": 200,
    "data": [{"url": "https://music.example.com/song.mp3"}],
}


# ---------------------------------------------------------------------------
# search() tests
# ---------------------------------------------------------------------------


class TestNeteaseMusicClientSearch:
    """Tests for NeteaseMusicClient.search()."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")
        self.client.client = MagicMock()

    async def test_search_normal(self):
        """正常返回搜索结果。"""
        self.client.client.get = AsyncMock(return_value=_make_response(200, SEARCH_OK_JSON))

        songs = await self.client.search("轻音乐", limit=5)

        assert len(songs) == 2
        assert isinstance(songs[0], Song)
        assert songs[0].id == 1001
        assert songs[0].name == "测试歌曲"
        assert songs[0].artists == ["歌手A"]
        assert songs[1].artists == ["歌手B", "歌手C"]

    async def test_search_500_retry_success(self):
        """第一次 500，第二次 200，验证重试后成功。"""
        self.client.client.get = AsyncMock(
            side_effect=[
                _make_response(500),
                _make_response(200, SEARCH_OK_JSON),
            ]
        )

        with patch("src.services.music_service.asyncio.sleep", new_callable=AsyncMock):
            songs = await self.client.search("轻音乐", max_retries=2)

        assert len(songs) == 2

    async def test_search_retries_exhausted(self):
        """始终 500，重试耗尽后返回空列表。"""
        self.client.client.get = AsyncMock(
            side_effect=[
                _make_response(500),
                _make_response(500),
                _make_response(500),
            ]
        )

        with patch("src.services.music_service.asyncio.sleep", new_callable=AsyncMock):
            songs = await self.client.search("轻音乐", max_retries=2)

        assert songs == []

    async def test_search_network_error_retry_success(self):
        """第一次网络异常，第二次成功。"""
        self.client.client.get = AsyncMock(
            side_effect=[
                httpx.ConnectError("connection refused"),
                _make_response(200, SEARCH_OK_JSON),
            ]
        )

        with patch("src.services.music_service.asyncio.sleep", new_callable=AsyncMock):
            songs = await self.client.search("轻音乐", max_retries=2)

        assert len(songs) == 2

    async def test_search_400_no_retry(self):
        """400 错误不触发重试。"""
        self.client.client.get = AsyncMock(return_value=_make_response(400))

        songs = await self.client.search("轻音乐", max_retries=2)

        assert songs == []
        # 只调用了一次，说明没有重试
        assert self.client.client.get.call_count == 1


# ---------------------------------------------------------------------------
# get_song_url() tests
# ---------------------------------------------------------------------------


class TestNeteaseMusicClientGetSongUrl:
    """Tests for NeteaseMusicClient.get_song_url()."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")
        self.client.client = MagicMock()
        # 清除类级别的 URL 缓存，避免测试间互相影响
        NeteaseMusicClient._url_cache.clear()

    async def test_get_song_url_normal(self):
        """正常返回 URL。"""
        self.client.client.get = AsyncMock(return_value=_make_response(200, SONG_URL_OK_JSON))

        url = await self.client.get_song_url(1001)

        assert url == "https://music.example.com/song.mp3"

    async def test_get_song_url_5xx_retry_success(self):
        """可恢复 5xx 重试后成功。503 应走快速降级测试覆盖。"""
        self.client.client.get = AsyncMock(
            side_effect=[
                _make_response(500),
                _make_response(200, SONG_URL_OK_JSON),
            ]
        )

        with patch("src.services.music_service.asyncio.sleep", new_callable=AsyncMock):
            url = await self.client.get_song_url(1001, retry=2)

        assert url == "https://music.example.com/song.mp3"

    async def test_get_song_url_null_url(self):
        """返回 null URL 时返回 None。"""
        json_data = {"code": 200, "data": [{"url": None}]}
        self.client.client.get = AsyncMock(return_value=_make_response(200, json_data))

        url = await self.client.get_song_url(1001)

        assert url is None
