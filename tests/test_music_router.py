"""Tests for music router endpoints."""

from dataclasses import dataclass
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.deps import get_current_user_optional
from src.api.routers.music import router

pytestmark = pytest.mark.api


# ---- helpers / fixtures ----


@dataclass
class FakeSong:
    id: int
    name: str
    artists: List[str]
    album: str
    duration: int
    url: Optional[str] = None


@dataclass
class FakeRecommendation:
    keywords: List[str]
    mood: str
    scene_type: str
    songs: List[FakeSong]
    environment: Optional[str] = None
    story_style: Optional[str] = None
    music_style: Optional[str] = None
    instruments: Optional[List[str]] = None
    pacing: Optional[str] = None
    time_weather: Optional[str] = None
    description: Optional[str] = None


def _make_songs(n: int, with_url: bool = True) -> List[FakeSong]:
    """Generate n fake songs, optionally without URL."""
    return [
        FakeSong(
            id=100 + i,
            name=f"Song {i}",
            artists=[f"Artist {i}"],
            album=f"Album {i}",
            duration=200000 + i * 1000,
            url=f"https://cdn.example.com/song{i}.mp3" if with_url else None,
        )
        for i in range(n)
    ]


def _make_recommendation(songs: List[FakeSong]) -> FakeRecommendation:
    return FakeRecommendation(
        keywords=["sad", "rain"],
        mood="melancholy",
        scene_type="outdoor",
        songs=songs,
        environment="rainy street",
        description="A sad melody",
    )


@pytest.fixture
def app():
    """Create a test FastAPI app with music router."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api")
    # Override auth dependency to return a dummy user
    test_app.dependency_overrides[get_current_user_optional] = lambda: 1
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


# ============================================================
# recommend_music endpoint  POST /api/music/recommend
# ============================================================


class TestRecommendMusic:
    """Tests for POST /api/music/recommend."""

    @patch("src.api.routers.music.get_music_service")
    def test_recommend_normal(self, mock_get_svc, client):
        """正常推荐 — 返回所有歌曲（均有 URL）。"""
        songs = _make_songs(3, with_url=True)
        rec = _make_recommendation(songs)

        svc = AsyncMock()
        svc.analyze_story_for_music.return_value = rec
        # get_song_play_url returns the URL already on the song
        svc.get_song_play_url = AsyncMock(
            side_effect=lambda sid: f"https://cdn.example.com/song{sid - 100}.mp3"
        )
        mock_get_svc.return_value = svc

        resp = client.post(
            "/api/music/recommend",
            json={"story_text": "It was raining."},
        )

        assert resp.status_code == 200
        data = resp.json()
        # Schema validation: MusicRecommendationResponse
        assert "keywords" in data
        assert isinstance(data["keywords"], list)
        assert "mood" in data
        assert isinstance(data["mood"], str)
        assert "scene_type" in data
        assert isinstance(data["scene_type"], str)
        assert "songs" in data
        assert isinstance(data["songs"], list)
        # Value checks
        assert data["mood"] == "melancholy"
        assert len(data["songs"]) == 3
        # Schema validation: each SongResponse
        for song in data["songs"]:
            assert "id" in song
            assert isinstance(song["id"], int)
            assert "name" in song
            assert isinstance(song["name"], str)
            assert "artists" in song
            assert isinstance(song["artists"], list)
            assert "album" in song
            assert isinstance(song["album"], str)
            assert "duration" in song
            assert isinstance(song["duration"], int)
            assert "url" in song
            assert song["url"] is not None

    @patch("src.api.routers.music.get_music_service")
    def test_recommend_filters_null_url(self, mock_get_svc, client):
        """部分歌曲 URL 为 null 时应被过滤。"""
        songs = _make_songs(4, with_url=False)
        rec = _make_recommendation(songs)

        # Only songs 100 and 102 get valid URLs
        url_map = {
            100: "https://cdn.example.com/a.mp3",
            102: "https://cdn.example.com/b.mp3",
        }
        svc = AsyncMock()
        svc.analyze_story_for_music.return_value = rec
        svc.get_song_play_url = AsyncMock(side_effect=lambda sid: url_map.get(sid))
        mock_get_svc.return_value = svc

        resp = client.post(
            "/api/music/recommend",
            json={"story_text": "A quiet night."},
        )

        assert resp.status_code == 200
        data = resp.json()
        # Schema validation
        assert "songs" in data
        assert isinstance(data["songs"], list)
        assert "mood" in data
        assert "keywords" in data
        assert len(data["songs"]) == 2
        # Validate filtered song schema
        for song in data["songs"]:
            assert "id" in song
            assert isinstance(song["id"], int)
            assert "name" in song
            assert "url" in song
            assert song["url"] is not None
        returned_ids = {s["id"] for s in data["songs"]}
        assert returned_ids == {100, 102}

    @patch("src.api.routers.music.get_music_service")
    def test_recommend_all_urls_null(self, mock_get_svc, client):
        """所有歌曲 URL 为 null 时返回空列表。"""
        songs = _make_songs(3, with_url=False)
        rec = _make_recommendation(songs)

        svc = AsyncMock()
        svc.analyze_story_for_music.return_value = rec
        svc.get_song_play_url = AsyncMock(return_value=None)
        mock_get_svc.return_value = svc

        resp = client.post(
            "/api/music/recommend",
            json={"story_text": "Silence."},
        )

        assert resp.status_code == 200
        data = resp.json()
        # Schema validation: still has required top-level fields
        assert "songs" in data
        assert isinstance(data["songs"], list)
        assert "mood" in data
        assert "keywords" in data
        assert "scene_type" in data
        assert data["songs"] == []


# ============================================================
# stream_song endpoint  GET /api/music/stream/{song_id}
# ============================================================


class TestStreamSong:
    """Tests for GET /api/music/stream/{song_id}."""

    @patch("src.api.routers.music.httpx.AsyncClient")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_normal(self, mock_get_svc, mock_async_client_cls, client):
        """正常流式返回音频数据。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(
            return_value="https://cdn.example.com/song.mp3"
        )
        mock_get_svc.return_value = svc

        # Build a fake httpx response
        fake_response = AsyncMock()
        fake_response.status_code = 200
        fake_response.headers = {"content-type": "audio/mpeg"}

        async def fake_iter():
            yield b"audio-chunk-1"
            yield b"audio-chunk-2"

        fake_response.aiter_bytes = MagicMock(return_value=fake_iter())
        fake_response.aclose = AsyncMock()

        fake_client = MagicMock()
        fake_client.build_request.return_value = MagicMock()
        fake_client.send = AsyncMock(return_value=fake_response)
        fake_client.aclose = AsyncMock()
        mock_async_client_cls.return_value = fake_client

        resp = client.get("/api/music/stream/12345")

        assert resp.status_code == 200
        # Schema validation: streaming response
        assert "audio" in resp.headers.get("content-type", "")
        assert b"audio-chunk-1" in resp.content

    @patch("src.api.routers.music.httpx.AsyncClient")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_no_content_length(
        self, mock_get_svc, mock_async_client_cls, client
    ):
        """流式响应不应包含 content-length 头。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(
            return_value="https://cdn.example.com/song.mp3"
        )
        mock_get_svc.return_value = svc

        fake_response = AsyncMock()
        fake_response.status_code = 200
        fake_response.headers = {"content-type": "audio/mpeg"}

        async def fake_iter():
            yield b"data"

        fake_response.aiter_bytes = MagicMock(return_value=fake_iter())
        fake_response.aclose = AsyncMock()

        fake_client = MagicMock()
        fake_client.build_request.return_value = MagicMock()
        fake_client.send = AsyncMock(return_value=fake_response)
        fake_client.aclose = AsyncMock()
        mock_async_client_cls.return_value = fake_client

        resp = client.get("/api/music/stream/12345")

        assert resp.status_code == 200
        assert "content-length" not in resp.headers

    @patch("src.api.routers.music.httpx.AsyncClient")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_correct_content_type(
        self, mock_get_svc, mock_async_client_cls, client
    ):
        """流式响应的 content-type 应为 audio 类型。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(
            return_value="https://cdn.example.com/song.mp3"
        )
        mock_get_svc.return_value = svc

        fake_response = AsyncMock()
        fake_response.status_code = 200
        fake_response.headers = {"content-type": "audio/mpeg"}

        async def fake_iter():
            yield b"data"

        fake_response.aiter_bytes = MagicMock(return_value=fake_iter())
        fake_response.aclose = AsyncMock()

        fake_client = MagicMock()
        fake_client.build_request.return_value = MagicMock()
        fake_client.send = AsyncMock(return_value=fake_response)
        fake_client.aclose = AsyncMock()
        mock_async_client_cls.return_value = fake_client

        resp = client.get("/api/music/stream/12345")

        assert resp.status_code == 200
        assert "audio" in resp.headers.get("content-type", "")

    @patch("src.api.routers.music.get_music_service")
    def test_stream_url_not_found(self, mock_get_svc, client):
        """歌曲 URL 获取失败时返回 404。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(return_value=None)
        mock_get_svc.return_value = svc

        resp = client.get("/api/music/stream/99999")

        assert resp.status_code == 404
        assert "not available" in resp.json()["detail"].lower()

    @patch("src.api.routers.music.httpx.AsyncClient")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_cdn_non_200(self, mock_get_svc, mock_async_client_cls, client):
        """CDN 返回非 200/206 且非 403/401 时应返回对应错误码。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(
            return_value="https://cdn.example.com/song.mp3"
        )
        mock_get_svc.return_value = svc

        fake_response = AsyncMock()
        fake_response.status_code = 500
        fake_response.headers = {}
        fake_response.aclose = AsyncMock()

        fake_client = MagicMock()
        fake_client.build_request.return_value = MagicMock()
        fake_client.send = AsyncMock(return_value=fake_response)
        fake_client.aclose = AsyncMock()
        mock_async_client_cls.return_value = fake_client

        resp = client.get("/api/music/stream/12345")

        assert resp.status_code == 500
        assert "CDN" in resp.json()["detail"]

    @patch("src.api.routers.music.httpx.AsyncClient")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_uses_small_chunk_size(
        self, mock_get_svc, mock_async_client_cls, client
    ):
        """流式代理应使用 8KB chunk_size 保证低延迟，避免 64KB 大 chunk 导致卡顿。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(
            return_value="https://cdn.example.com/song.mp3"
        )
        mock_get_svc.return_value = svc

        fake_response = AsyncMock()
        fake_response.status_code = 200
        fake_response.headers = {"content-type": "audio/mpeg"}

        async def fake_iter():
            yield b"chunk"

        fake_response.aiter_bytes = MagicMock(return_value=fake_iter())
        fake_response.aclose = AsyncMock()

        fake_client = MagicMock()
        fake_client.build_request.return_value = MagicMock()
        fake_client.send = AsyncMock(return_value=fake_response)
        fake_client.aclose = AsyncMock()
        mock_async_client_cls.return_value = fake_client

        resp = client.get("/api/music/stream/12345")

        assert resp.status_code == 200
        # 验证 aiter_bytes 被调用且 chunk_size=8192
        fake_response.aiter_bytes.assert_called_once()
        call_kwargs = fake_response.aiter_bytes.call_args.kwargs
        assert call_kwargs.get("chunk_size") == 8192

    @patch("src.api.routers.music.httpx.AsyncClient")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_cdn_403_retry_success(
        self, mock_get_svc, mock_async_client_cls, client
    ):
        """CDN 返回 403 时应刷新 URL 并重试，重试成功则正常返回。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(
            side_effect=[
                "https://cdn.example.com/old.mp3",
                "https://cdn.example.com/fresh.mp3",
            ]
        )
        mock_get_svc.return_value = svc

        # 第一次请求返回 403，第二次返回 200
        fake_403 = AsyncMock()
        fake_403.status_code = 403
        fake_403.headers = {}
        fake_403.aclose = AsyncMock()

        async def fresh_iter():
            yield b"fresh-audio"

        fake_200 = AsyncMock()
        fake_200.status_code = 200
        fake_200.headers = {"content-type": "audio/mpeg"}
        fake_200.aiter_bytes = MagicMock(return_value=fresh_iter())
        fake_200.aclose = AsyncMock()

        fake_client = MagicMock()
        fake_client.build_request.return_value = MagicMock()
        fake_client.send = AsyncMock(side_effect=[fake_403, fake_200])
        fake_client.aclose = AsyncMock()
        mock_async_client_cls.return_value = fake_client

        resp = client.get("/api/music/stream/12345")

        assert resp.status_code == 200
        assert b"fresh-audio" in resp.content

    @patch("src.api.routers.music.httpx.AsyncClient")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_range_request(self, mock_get_svc, mock_async_client_cls, client):
        """Range 请求头应被转发到 CDN，并返回 206 + content-range。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(
            return_value="https://cdn.example.com/song.mp3"
        )
        mock_get_svc.return_value = svc

        async def partial_iter():
            yield b"partial-data"

        fake_response = AsyncMock()
        fake_response.status_code = 206
        fake_response.headers = {
            "content-type": "audio/mpeg",
            "content-range": "bytes 1000-2000/5000",
        }
        fake_response.aiter_bytes = MagicMock(return_value=partial_iter())
        fake_response.aclose = AsyncMock()

        fake_client = MagicMock()
        fake_client.build_request.return_value = MagicMock()
        fake_client.send = AsyncMock(return_value=fake_response)
        fake_client.aclose = AsyncMock()
        mock_async_client_cls.return_value = fake_client

        resp = client.get(
            "/api/music/stream/12345", headers={"range": "bytes=1000-2000"}
        )

        assert resp.status_code == 206
        assert resp.headers.get("content-range") == "bytes 1000-2000/5000"
        assert b"partial-data" in resp.content
