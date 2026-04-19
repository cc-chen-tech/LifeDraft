"""音乐混合缓存池集成测试 (Layer 4)

验证缓存池的完整行为：命中、miss、随机选择、URL刷新等。
"""

import time
from unittest.mock import AsyncMock

import pytest

from src.services.music_service import CachedSong, CachedMusicPool, MusicService, Song


class TestRandomSelectSongs:
    """验证 _random_select_songs 方法。"""

    def _make_pool(self, count: int) -> CachedMusicPool:
        """创建指定数量的测试歌曲池。"""
        songs = []
        for i in range(count):
            songs.append(
                CachedSong(
                    id=1000 + i,
                    name=f"歌曲{i}",
                    artists=[f"歌手{i}"],
                    album=f"专辑{i}",
                    duration=200000 + i * 1000,
                    url=f"https://cdn.example.com/song{i}.mp3",
                    url_expires_at=time.time() + 480,
                    verified_at=time.time(),
                )
            )
        return CachedMusicPool(
            analysis={"mood": "悲伤"},
            verified_songs=songs,
            created_at=time.time(),
        )

    def test_returns_5_to_8_songs(self):
        """返回数量在 5-8 之间。"""
        pool = self._make_pool(25)
        service = MusicService()

        for _ in range(20):
            result = service._random_select_songs(pool)
            assert 5 <= len(result) <= 8, (
                f"返回数量 {len(result)} 不在 5-8 范围内"
            )

    def test_returns_unique_songs(self):
        """返回的歌曲不重复。"""
        pool = self._make_pool(25)
        service = MusicService()

        result = service._random_select_songs(pool)
        ids = [s.id for s in result]
        assert len(ids) == len(set(ids)), "返回的歌曲 ID 必须唯一"

    def test_all_returned_songs_have_url(self):
        """返回的歌曲全部有 URL。"""
        pool = self._make_pool(25)
        service = MusicService()

        result = service._random_select_songs(pool)
        for song in result:
            assert song.url, f"歌曲 {song.name} 必须有 URL"

    def test_returns_songs_from_pool(self):
        """返回的歌曲全部来自池中。"""
        pool = self._make_pool(25)
        service = MusicService()
        pool_ids = {s.id for s in pool.verified_songs}

        result = service._random_select_songs(pool)
        for song in result:
            assert song.id in pool_ids, f"歌曲 {song.id} 不在池中"

    def test_pool_with_less_than_5_songs_returns_all(self):
        """池中小于 5 首时返回全部。"""
        pool = self._make_pool(3)
        service = MusicService()

        result = service._random_select_songs(pool)
        assert len(result) == 3


class TestGetOrBuildPool:
    """验证 _get_or_build_pool 方法。"""

    @pytest.fixture(autouse=True)
    def _clear_caches(self):
        """每个测试前清除缓存。"""
        MusicService._analysis_cache.clear()
        MusicService._pool_cache.clear()

    async def test_cache_miss_builds_new_pool(self):
        """缓存未命中时构建新池。"""
        service = MusicService()

        # Mock AI analysis
        service._analyze_story_mood = AsyncMock(return_value={
            "mood": "悲伤",
            "keywords": ["伤感", "抒情"],
            "scene_type": "叙事",
        })

        # Mock search to return songs
        service.music_client.search = AsyncMock(return_value=[
            Song(id=1001, name="歌曲1", artists=["A"], album="X", duration=200000),
            Song(id=1002, name="歌曲2", artists=["B"], album="Y", duration=210000),
        ])

        # Mock get_song_url to return URLs
        service.music_client.get_song_url = AsyncMock(
            side_effect=lambda song_id: f"https://cdn.example.com/{song_id}.mp3"
        )

        pool = await service._get_or_build_pool("test_story", refresh=False)

        assert pool is not None
        assert isinstance(pool, CachedMusicPool)
        assert pool.analysis["mood"] == "悲伤"
        assert len(pool.verified_songs) >= 0

    async def test_cache_hit_returns_existing_pool(self):
        """缓存命中时返回现有池，不重新搜索。"""
        service = MusicService()
        story_text = "缓存测试故事"
        story_hash = service._story_hash(story_text)

        # 预填充缓存
        existing_pool = CachedMusicPool(
            analysis={"mood": "欢快"},
            verified_songs=[
                CachedSong(
                    id=2001, name="缓存歌曲", artists=["C"], album="Z",
                    duration=180000, url="https://cdn.example.com/2001.mp3",
                    url_expires_at=time.time() + 480, verified_at=time.time(),
                )
            ],
            created_at=time.time(),
        )
        MusicService._pool_cache[story_hash] = (existing_pool, time.time())

        # Mock search — 如果被调用就会失败
        service.music_client.search = AsyncMock(
            side_effect=Exception("Should not be called when cache hits")
        )

        pool = await service._get_or_build_pool(story_text, refresh=False)

        assert pool is existing_pool
        assert pool.verified_songs[0].name == "缓存歌曲"
        service.music_client.search.assert_not_called()

    async def test_cache_expired_rebuilds_pool(self):
        """缓存过期时重建池。"""
        service = MusicService()
        story_hash = "test_expired"

        # 预填充过期缓存
        old_pool = CachedMusicPool(
            analysis={"mood": "旧情绪"},
            verified_songs=[],
            created_at=time.time() - 7200,  # 2 hours ago
        )
        MusicService._pool_cache[story_hash] = (old_pool, time.time() - 7200)

        # Mock new analysis
        service._analyze_story_mood = AsyncMock(return_value={
            "mood": "新情绪",
            "keywords": ["新关键词"],
            "scene_type": "叙事",
        })

        # Mock search
        service.music_client.search = AsyncMock(return_value=[
            Song(id=3001, name="新歌曲", artists=["D"], album="W", duration=190000),
        ])

        service.music_client.get_song_url = AsyncMock(
            return_value="https://cdn.example.com/3001.mp3"
        )

        pool = await service._get_or_build_pool("test_expired", refresh=False)

        assert pool is not old_pool
        assert pool.analysis["mood"] == "新情绪"
        assert len(pool.verified_songs) >= 1

    async def test_refresh_reuses_analysis_rebuilds_pool(self):
        """刷新模式复用分析结果但重建池。"""
        service = MusicService()
        story_text = "刷新测试故事"
        story_hash = service._story_hash(story_text)

        # 预填充缓存
        existing_pool = CachedMusicPool(
            analysis={"mood": "悲伤", "keywords": ["伤感", "抒情"]},
            verified_songs=[],
            created_at=time.time(),
        )
        MusicService._pool_cache[story_hash] = (existing_pool, time.time())
        MusicService._analysis_cache[story_hash] = (
            {"mood": "悲伤", "keywords": ["伤感", "抒情"]},
            time.time(),
        )

        # Mock AI分析 — 不应该被调用
        service._analyze_story_mood = AsyncMock(
            side_effect=Exception("Should not re-analyze on refresh")
        )

        # Mock search
        service.music_client.search = AsyncMock(return_value=[
            Song(id=4001, name="刷新歌曲", artists=["E"], album="V", duration=220000),
        ])

        service.music_client.get_song_url = AsyncMock(
            return_value="https://cdn.example.com/4001.mp3"
        )

        pool = await service._get_or_build_pool(story_text, refresh=True)

        assert pool.analysis["mood"] == "悲伤"
        service._analyze_story_mood.assert_not_called()
        assert len(pool.verified_songs) >= 1
