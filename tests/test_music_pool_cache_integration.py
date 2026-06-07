"""音乐混合缓存池集成测试 (Layer 4)

验证缓存池的完整行为：命中、miss、随机选择、URL刷新等。
"""

import time
from unittest.mock import AsyncMock

import pytest

from src.services.music_service import (CachedMusicPool, CachedSong,
                                        MusicService, Song)


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
            assert 5 <= len(result) <= 8, f"返回数量 {len(result)} 不在 5-8 范围内"

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
        MusicService._refresh_cursors.clear()

    async def test_cache_miss_builds_new_pool(self):
        """缓存未命中时构建新池。"""
        service = MusicService()

        # Mock AI analysis
        service._analyze_story_mood = AsyncMock(
            return_value={
                "mood": "悲伤",
                "keywords": ["伤感", "抒情"],
                "scene_type": "叙事",
            }
        )

        # Mock search to return songs
        service.music_client.search = AsyncMock(
            return_value=[
                Song(id=1001, name="歌曲1", artists=["A"], album="X", duration=200000),
                Song(id=1002, name="歌曲2", artists=["B"], album="Y", duration=210000),
            ]
        )

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
                    id=2001,
                    name="缓存歌曲",
                    artists=["C"],
                    album="Z",
                    duration=180000,
                    url="https://cdn.example.com/2001.mp3",
                    url_expires_at=time.time() + 480,
                    verified_at=time.time(),
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
        service._analyze_story_mood = AsyncMock(
            return_value={
                "mood": "新情绪",
                "keywords": ["新关键词"],
                "scene_type": "叙事",
            }
        )

        # Mock search
        service.music_client.search = AsyncMock(
            return_value=[
                Song(id=3001, name="新歌曲", artists=["D"], album="W", duration=190000),
            ]
        )

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
        service.music_client.search = AsyncMock(
            return_value=[
                Song(id=4001, name="刷新歌曲", artists=["E"], album="V", duration=220000),
            ]
        )

        service.music_client.get_song_url = AsyncMock(
            return_value="https://cdn.example.com/4001.mp3"
        )

        pool = await service._get_or_build_pool(story_text, refresh=True)

        assert pool.analysis["mood"] == "悲伤"
        service._analyze_story_mood.assert_not_called()
        assert len(pool.verified_songs) >= 1

    async def test_refresh_advances_search_query_cursor(self):
        """换一批应复用分析但推进搜索 query，避免同批候选原样返回。"""
        service = MusicService()
        story_text = "现代医院里，主角发现医疗数据造假后被追捕，只能连夜逃亡。"
        story_hash = service._story_hash(story_text)
        analysis = {
            "mood": "紧张",
            "scene_type": "追捕逃亡",
            "environment": "现代医院",
            "story_style": "医疗悬疑",
            "pacing": "急促",
            "energy": "高",
            "instruments": ["电子合成器", "低音弦乐"],
            "search_queries": ["现代悬疑 纯音乐", "医疗悬疑 氛围音乐", "追捕 紧张 配乐"],
            "negative_cues": ["恋爱", "情歌", "歌词", "流行人声"],
        }
        MusicService._analysis_cache[story_hash] = (analysis, time.time())
        MusicService._pool_cache[story_hash] = (
            CachedMusicPool(analysis=analysis, verified_songs=[], created_at=time.time()),
            time.time(),
        )
        searched_queries: list[str] = []

        async def fake_search(keyword: str, limit: int = 10):
            searched_queries.append(keyword)
            song_id = 9000 + len(searched_queries)
            return [
                Song(
                    id=song_id,
                    name=f"{keyword} 候选",
                    artists=["Score"],
                    album="影视配乐",
                    duration=120000,
                )
            ]

        service._analyze_story_mood = AsyncMock(
            side_effect=Exception("Should not re-analyze on refresh")
        )
        service.music_client.search = AsyncMock(side_effect=fake_search)
        service.music_client.get_song_url = AsyncMock(
            side_effect=lambda song_id: f"https://cdn.example.com/{song_id}.mp3"
        )

        first_pool = await service._get_or_build_pool(story_text, refresh=True)
        first_query = searched_queries[0]
        searched_queries.clear()

        second_pool = await service._get_or_build_pool(story_text, refresh=True)
        second_query = searched_queries[0]

        service._analyze_story_mood.assert_not_called()
        assert first_pool.query_cursor != second_pool.query_cursor
        assert first_query != second_query

    async def test_supplement_pool_filters_prompt_leak_song_titles(self):
        """网易云搜索结果中的 LLM 提示词泄漏标题不应进入推荐池。"""
        service = MusicService()
        pool = CachedMusicPool(
            analysis={
                "mood": "紧张",
                "scene_type": "职场危机",
                "environment": "现代都市",
                "search_queries": ["现代悬疑 纯音乐"],
            },
            verified_songs=[],
            created_at=time.time(),
        )
        service.music_client.search = AsyncMock(
            return_value=[
                Song(
                    id=9101,
                    name="请提供需要分析的文本内容，我将按照您的要求提取歌名信息。若输入文本没有歌名，则输出0",
                    artists=["用户415329033"],
                    album="请提供需要分析的文本内容",
                    duration=182768,
                ),
                Song(
                    id=9102,
                    name="都市暗涌",
                    artists=["影视配乐"],
                    album="现代悬疑氛围",
                    duration=120000,
                ),
            ]
        )
        service.music_client.get_song_url = AsyncMock(
            side_effect=lambda song_id: f"https://cdn.example.com/{song_id}.mp3"
        )

        await service._supplement_pool(pool)

        assert [song.id for song in pool.verified_songs] == [9102]

    async def test_supplement_pool_filters_negative_cue_songs_for_story_context(self):
        """与故事负向 cue 明确冲突的歌曲不应进入推荐池。"""
        service = MusicService()
        pool = CachedMusicPool(
            analysis={
                "mood": "紧张",
                "scene_type": "职场数据造假",
                "environment": "现代都市",
                "search_queries": ["现代悬疑 纯音乐"],
                "negative_cues": ["type beat", "喜欢你", "情歌", "流行人声"],
            },
            verified_songs=[],
            created_at=time.time(),
        )
        service.music_client.search = AsyncMock(
            return_value=[
                Song(
                    id=9201,
                    name="双截棍type beat",
                    artists=["To."],
                    album="累了",
                    duration=178217,
                ),
                Song(
                    id=9202,
                    name="喜欢你-0.8x",
                    artists=["翻唱"],
                    album="流行情歌",
                    duration=180000,
                ),
                Song(
                    id=9203,
                    name="都市冷光",
                    artists=["Score Lab"],
                    album="现代悬疑配乐",
                    duration=150000,
                ),
            ]
        )
        service.music_client.get_song_url = AsyncMock(
            side_effect=lambda song_id: f"https://cdn.example.com/{song_id}.mp3"
        )

        await service._supplement_pool(pool)

        assert [song.id for song in pool.verified_songs] == [9203]


class TestRefreshPoolUrls:
    """验证 _refresh_pool_urls 方法。"""

    @pytest.fixture(autouse=True)
    def _clear_caches(self):
        MusicService._analysis_cache.clear()
        MusicService._pool_cache.clear()
        MusicService._refresh_cursors.clear()

    async def test_refreshes_expired_urls(self):
        """过期的 URL 被重新获取。"""
        service = MusicService()
        now = time.time()

        # 创建有过期 URL 的池
        pool = CachedMusicPool(
            analysis={"mood": "悲伤"},
            verified_songs=[
                CachedSong(
                    id=5001,
                    name="过期歌曲",
                    artists=["F"],
                    album="U",
                    duration=200000,
                    url="https://old.example.com/5001.mp3",
                    url_expires_at=now - 10,  # 已过期
                    verified_at=now - 600,
                ),
            ],
            created_at=now,
        )

        # Mock URL refresh
        service.music_client.get_song_url = AsyncMock(
            return_value="https://fresh.example.com/5001.mp3"
        )

        await service._refresh_pool_urls(pool)

        assert pool.verified_songs[0].url == "https://fresh.example.com/5001.mp3"
        assert pool.verified_songs[0].url_expires_at > now

    async def test_removes_song_when_url_refresh_fails(self):
        """URL 刷新失败时从池中移除歌曲。"""
        service = MusicService()
        now = time.time()

        pool = CachedMusicPool(
            analysis={"mood": "悲伤"},
            verified_songs=[
                CachedSong(
                    id=6001,
                    name="失败歌曲",
                    artists=["G"],
                    album="T",
                    duration=200000,
                    url="https://old.example.com/6001.mp3",
                    url_expires_at=now - 10,  # 已过期
                    verified_at=now - 600,
                ),
            ],
            created_at=now,
        )

        # Mock URL refresh failure
        service.music_client.get_song_url = AsyncMock(return_value=None)

        await service._refresh_pool_urls(pool)

        assert len(pool.verified_songs) == 0

    async def test_keeps_fresh_urls_unchanged(self):
        """未过期的 URL 保持不变。"""
        service = MusicService()
        now = time.time()

        pool = CachedMusicPool(
            analysis={"mood": "悲伤"},
            verified_songs=[
                CachedSong(
                    id=7001,
                    name="新鲜歌曲",
                    artists=["H"],
                    album="S",
                    duration=200000,
                    url="https://fresh.example.com/7001.mp3",
                    url_expires_at=now + 400,  # 未过期
                    verified_at=now,
                ),
            ],
            created_at=now,
        )

        # Mock that should NOT be called
        service.music_client.get_song_url = AsyncMock(
            side_effect=Exception("Should not refresh fresh URLs")
        )

        await service._refresh_pool_urls(pool)

        assert pool.verified_songs[0].url == "https://fresh.example.com/7001.mp3"
        service.music_client.get_song_url.assert_not_called()

    async def test_supplemental_search_when_pool_too_small(self):
        """池歌曲 < 5 首时触发补充搜索。"""
        service = MusicService()
        now = time.time()

        pool = CachedMusicPool(
            analysis={"mood": "悲伤"},
            verified_songs=[
                CachedSong(
                    id=8001,
                    name="唯一歌曲",
                    artists=["I"],
                    album="R",
                    duration=200000,
                    url="https://cdn.example.com/8001.mp3",
                    url_expires_at=now + 400,
                    verified_at=now,
                ),
            ],
            created_at=now,
        )

        # Mock search for supplemental
        service.music_client.search = AsyncMock(
            return_value=[
                Song(id=8002, name="补充歌曲", artists=["J"], album="Q", duration=210000),
            ]
        )
        service.music_client.get_song_url = AsyncMock(
            return_value="https://cdn.example.com/8002.mp3"
        )

        await service._refresh_pool_urls(pool)

        service.music_client.search.assert_called()
        assert len(pool.verified_songs) >= 2


class TestAnalyzeStoryForMusicWithPool:
    """验证 analyze_story_for_music 使用缓存池。"""

    @pytest.fixture(autouse=True)
    def _clear_caches(self):
        MusicService._analysis_cache.clear()
        MusicService._pool_cache.clear()

    async def test_returns_music_recommendation(self):
        """返回 MusicRecommendation 类型。"""
        service = MusicService()

        service._analyze_story_mood = AsyncMock(
            return_value={
                "mood": "悲伤",
                "keywords": ["伤感"],
                "scene_type": "叙事",
            }
        )
        service.music_client.search = AsyncMock(
            return_value=[
                Song(id=9001, name="歌曲1", artists=["A"], album="X", duration=200000),
                Song(id=9002, name="歌曲2", artists=["B"], album="Y", duration=210000),
            ]
        )
        service.music_client.get_song_url = AsyncMock(
            side_effect=lambda song_id: f"https://cdn.example.com/{song_id}.mp3"
        )

        result = await service.analyze_story_for_music("一个悲伤的故事")

        from src.services.music_service import MusicRecommendation

        assert isinstance(result, MusicRecommendation)
        assert result.mood == "悲伤"

    async def test_returns_5_to_8_songs(self):
        """返回 5-8 首歌曲。"""
        service = MusicService()

        service._analyze_story_mood = AsyncMock(
            return_value={
                "mood": "悲伤",
                "keywords": ["伤感"],
                "scene_type": "叙事",
            }
        )

        # 生成足够多的歌曲
        songs = []
        for i in range(30):
            songs.append(
                Song(
                    id=10000 + i,
                    name=f"歌曲{i}",
                    artists=[f"歌手{i}"],
                    album=f"专辑{i}",
                    duration=200000 + i * 1000,
                )
            )
        service.music_client.search = AsyncMock(return_value=songs)
        service.music_client.get_song_url = AsyncMock(
            side_effect=lambda song_id: f"https://cdn.example.com/{song_id}.mp3"
        )

        result = await service.analyze_story_for_music("一个悲伤的故事")

        assert 5 <= len(result.songs) <= 8, f"返回 {len(result.songs)} 首，不在 5-8 范围内"

    async def test_all_returned_songs_have_url(self):
        """返回的歌曲全部有 URL。"""
        service = MusicService()

        service._analyze_story_mood = AsyncMock(
            return_value={
                "mood": "悲伤",
                "keywords": ["伤感"],
                "scene_type": "叙事",
            }
        )

        songs = []
        for i in range(30):
            songs.append(
                Song(
                    id=11000 + i,
                    name=f"歌曲{i}",
                    artists=[f"歌手{i}"],
                    album=f"专辑{i}",
                    duration=200000 + i * 1000,
                )
            )
        service.music_client.search = AsyncMock(return_value=songs)
        service.music_client.get_song_url = AsyncMock(
            side_effect=lambda song_id: f"https://cdn.example.com/{song_id}.mp3"
        )

        result = await service.analyze_story_for_music("一个悲伤的故事")

        for song in result.songs:
            assert song.url, f"歌曲 {song.name} 必须有 URL"

    async def test_cache_hit_returns_from_pool(self):
        """缓存命中时从池中返回。"""
        service = MusicService()
        story_text = "缓存测试故事"
        story_hash = service._story_hash(story_text)

        # 预填充缓存池
        pool = CachedMusicPool(
            analysis={"mood": "欢快"},
            verified_songs=[
                CachedSong(
                    id=12001,
                    name="缓存歌曲",
                    artists=["C"],
                    album="Z",
                    duration=180000,
                    url="https://cdn.example.com/12001.mp3",
                    url_expires_at=time.time() + 480,
                    verified_at=time.time(),
                )
                for _ in range(10)
            ],
            created_at=time.time(),
        )
        MusicService._pool_cache[story_hash] = (pool, time.time())

        # Mock search — 不应该被调用
        service.music_client.search = AsyncMock(
            side_effect=Exception("Should not search when pool cache hits")
        )

        result = await service.analyze_story_for_music(story_text)

        assert result.mood == "欢快"
        service.music_client.search.assert_not_called()
