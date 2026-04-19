"""音乐混合缓存池集成测试 (Layer 4)

验证缓存池的完整行为：命中、miss、随机选择、URL刷新等。
"""

import time

from src.services.music_service import CachedSong, CachedMusicPool, MusicService


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
