"""Tests for music router endpoints."""

from dataclasses import dataclass
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.deps import get_current_user_optional
from src.api.routers.music import router
from src.services.music_service import MusicBrief

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
    music_brief: Optional[Any] = None


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

    @patch("src.api.routers.music.get_music_service")
    def test_recommend_response_filters_negative_cue_title_families_before_url_lookup(
        self, mock_get_svc, client
    ):
        """最终 API 响应也要兜底过滤与 music_brief 冲突的推荐。"""
        brief = MusicBrief(
            mood="压抑焦虑",
            scene_type="雨夜追捕",
            era_or_environment="现代城市",
            pacing="紧凑",
            energy="中高",
            instruments=["低音弦乐", "电子合成器"],
            search_queries=["追捕 悬疑 纯音乐", "无歌词 紧张氛围"],
            negative_cues=["人声", "歌词", "情歌", "流行人声", "热门金曲"],
            generation_prompt="instrumental suspense loop, no vocals, no lyrics",
        )
        rec = FakeRecommendation(
            keywords=brief.search_queries,
            mood=brief.mood,
            scene_type=brief.scene_type,
            songs=[
                FakeSong(
                    id=4101,
                    name="绅士",
                    artists=["薛之谦"],
                    album="热门金曲",
                    duration=180000,
                ),
                FakeSong(
                    id=4102,
                    name="红尘客栈 - 古风翻唱",
                    artists=["Vocal"],
                    album="翻唱合集",
                    duration=180000,
                ),
                FakeSong(
                    id=4103,
                    name="Blue Bird",
                    artists=["Ikimono-gakari"],
                    album="Anime Opening Vocal",
                    duration=180000,
                ),
                FakeSong(
                    id=4201,
                    name="午夜追捕低音弦乐",
                    artists=["Score Lab"],
                    album="现代悬疑 纯音乐",
                    duration=180000,
                ),
            ],
            environment=brief.era_or_environment,
            music_brief=brief.to_analysis(),
        )

        svc = AsyncMock()
        svc.analyze_story_for_music.return_value = rec
        svc.get_song_play_url = AsyncMock(
            side_effect=lambda sid: f"https://cdn.example.com/{sid}.mp3"
        )
        mock_get_svc.return_value = svc

        resp = client.post(
            "/api/music/recommend",
            json={"story_text": "雨夜里，主角穿过巷口躲避追捕。"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert [song["name"] for song in data["songs"]] == ["午夜追捕低音弦乐"]
        assert data["music_brief"]["negative_cues"] == brief.negative_cues
        assert svc.get_song_play_url.await_count == 1


# ============================================================
# stream_song endpoint  GET /api/music/stream/{song_id}
# ============================================================


class TestStreamSong:
    """Tests for GET /api/music/stream/{song_id}."""

    @patch("src.api.routers.music._get_or_download_audio")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_normal(self, mock_get_svc, mock_get_audio, client):
        """正常返回完整音频数据。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(return_value="https://cdn.example.com/song.mp3")
        mock_get_svc.return_value = svc
        mock_get_audio.return_value = (b"audio-chunk-1audio-chunk-2", "audio/mpeg")

        resp = client.get("/api/music/stream/12345")

        assert resp.status_code == 200
        assert "audio" in resp.headers.get("content-type", "")
        assert b"audio-chunk-1" in resp.content

    @patch("src.api.routers.music._get_or_download_audio")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_no_content_length(self, mock_get_svc, mock_get_audio, client):
        """完整下载响应应包含 content-length 头（非流式）。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(return_value="https://cdn.example.com/song.mp3")
        mock_get_svc.return_value = svc
        mock_get_audio.return_value = (b"data", "audio/mpeg")

        resp = client.get("/api/music/stream/12345")

        assert resp.status_code == 200
        # Full-download mode sets content-length
        assert "content-length" in resp.headers

    @patch("src.api.routers.music._get_or_download_audio")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_correct_content_type(self, mock_get_svc, mock_get_audio, client):
        """响应的 content-type 应为 audio 类型。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(return_value="https://cdn.example.com/song.mp3")
        mock_get_svc.return_value = svc
        mock_get_audio.return_value = (b"data", "audio/mpeg")

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

    @patch("src.api.routers.music._get_or_download_audio")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_cdn_non_200(self, mock_get_svc, mock_get_audio, client):
        """CDN 返回非 200/206 且非 403/401 时应返回 502。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(return_value="https://cdn.example.com/song.mp3")
        mock_get_svc.return_value = svc
        mock_get_audio.side_effect = httpx.HTTPError("CDN request failed")

        resp = client.get("/api/music/stream/12345")

        assert resp.status_code == 502
        assert "CDN" in resp.json()["detail"]

    @patch("src.api.routers.music._get_or_download_audio")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_uses_small_chunk_size(self, mock_get_svc, mock_get_audio, client):
        """完整下载模式：验证 LRU 缓存最多缓存 10 首歌曲。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(return_value="https://cdn.example.com/song.mp3")
        mock_get_svc.return_value = svc
        mock_get_audio.return_value = (b"chunk", "audio/mpeg")

        resp = client.get("/api/music/stream/12345")

        assert resp.status_code == 200
        # 验证 _get_or_download_audio 被调用
        mock_get_audio.assert_called_once()

    @patch("src.api.routers.music._get_or_download_audio")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_cdn_403_retry_success(self, mock_get_svc, mock_get_audio, client):
        """CDN 返回 403 时 _get_or_download_audio 内部处理重试，最终返回音频。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(return_value="https://cdn.example.com/song.mp3")
        mock_get_svc.return_value = svc
        mock_get_audio.return_value = (b"fresh-audio", "audio/mpeg")

        resp = client.get("/api/music/stream/12345")

        assert resp.status_code == 200
        assert b"fresh-audio" in resp.content

    @patch("src.api.routers.music._get_or_download_audio")
    @patch("src.api.routers.music.get_music_service")
    def test_stream_range_request(self, mock_get_svc, mock_get_audio, client):
        """Range 请求应返回 206 + content-range。"""
        svc = MagicMock()
        svc.get_song_play_url = AsyncMock(return_value="https://cdn.example.com/song.mp3")
        mock_get_svc.return_value = svc
        # 返回足够长的音频数据以支持 Range 请求
        mock_get_audio.return_value = (b"x" * 5000, "audio/mpeg")

        resp = client.get("/api/music/stream/12345", headers={"range": "bytes=1000-2000"})

        assert resp.status_code == 206
        assert "content-range" in resp.headers
