"""音乐混合缓存池契约测试 (Layer 3)

验证 CachedSong、CachedMusicPool 和 MusicService 缓存池类变量的接口契约。
"""


class TestCachedSongStructure:
    """验证 CachedSong 数据结构契约。"""

    def test_cached_song_has_required_fields(self):
        from src.services.music_service import CachedSong

        song = CachedSong(
            id=1001,
            name="测试歌曲",
            artists=["歌手A"],
            album="专辑X",
            duration=240000,
            url="https://cdn.example.com/song.mp3",
            url_expires_at=9999999999.0,
            verified_at=1000.0,
        )
        assert song.id == 1001
        assert song.name == "测试歌曲"
        assert song.artists == ["歌手A"]
        assert song.album == "专辑X"
        assert song.duration == 240000
        assert song.url == "https://cdn.example.com/song.mp3"
        assert song.url_expires_at == 9999999999.0
        assert song.verified_at == 1000.0


class TestCachedMusicPoolStructure:
    """验证 CachedMusicPool 数据结构契约。"""

    def test_pool_has_required_fields(self):
        from src.services.music_service import CachedMusicPool, CachedSong

        song = CachedSong(
            id=1001,
            name="测试歌曲",
            artists=["歌手A"],
            album="专辑X",
            duration=240000,
            url="https://cdn.example.com/song.mp3",
            url_expires_at=9999999999.0,
            verified_at=1000.0,
        )
        pool = CachedMusicPool(
            analysis={"mood": "悲伤", "keywords": ["伤感", "抒情"]},
            verified_songs=[song],
            created_at=1000.0,
        )
        assert pool.analysis == {"mood": "悲伤", "keywords": ["伤感", "抒情"]}
        assert len(pool.verified_songs) == 1
        assert pool.verified_songs[0].id == 1001
        assert pool.created_at == 1000.0


class TestMusicServicePoolCacheContract:
    """验证 MusicService 缓存池类变量契约。"""

    def test_pool_cache_is_class_variable(self):
        """_pool_cache 必须是类级变量，跨实例共享。"""
        from src.services.music_service import MusicService

        assert (
            "_pool_cache" in MusicService.__dict__
        ), "_pool_cache 必须是类级变量，确保跨实例缓存共享"

    def test_pool_cache_ttl_value(self):
        """POOL_CACHE_TTL 应为 3600 秒（1 小时）。"""
        from src.services.music_service import MusicService

        assert MusicService.POOL_CACHE_TTL == 3600, "POOL_CACHE_TTL 必须为 3600 秒（1 小时）"

    def test_pool_cache_entry_structure(self):
        """缓存项应为 (CachedMusicPool, timestamp) 元组。"""
        import time

        from src.services.music_service import (CachedMusicPool, CachedSong,
                                                MusicService)

        pool = CachedMusicPool(
            analysis={"mood": "悲伤"},
            verified_songs=[
                CachedSong(
                    id=1001,
                    name="测试",
                    artists=["A"],
                    album="X",
                    duration=1000,
                    url="https://cdn.example.com/song.mp3",
                    url_expires_at=time.time() + 480,
                    verified_at=time.time(),
                )
            ],
            created_at=time.time(),
        )
        MusicService._pool_cache["test_key"] = (pool, time.time())

        cached = MusicService._pool_cache.get("test_key")
        assert cached is not None
        assert isinstance(cached, tuple), "缓存项必须是元组"
        assert len(cached) == 2, "缓存项必须是 (pool, timestamp) 二元组"
        assert isinstance(cached[0], CachedMusicPool), "第一个元素必须是 CachedMusicPool"
        assert isinstance(cached[1], float), "第二个元素必须是时间戳（float）"

        # 清理
        del MusicService._pool_cache["test_key"]
