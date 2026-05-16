# 音乐混合缓存池 Implementation Plan

> Status: Implemented (historical implementation plan)  
> Last reviewed: 2026-04-19

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hybrid cache pool to MusicService that caches AI analysis results + verified songs with URLs, returning 5-8 random songs per request.

**Architecture:** Class-level in-memory cache on `MusicService` keyed by story hash. Pool contains 20-25 verified songs. Two TTLs: pool TTL (60min) and per-song URL TTL (8min). Existing URL cache on `NeteaseMusicClient` stays as-is.

**Tech Stack:** Python 3.9, FastAPI, pytest, existing mock patterns in `tests/test_music_service.py`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/services/music_service.py` | Modify | Add `CachedSong`, `CachedMusicPool`, `_pool_cache`, `_get_or_build_pool()`, `_refresh_pool_urls()`, `_random_select_songs()` |
| `tests/test_music_pool_cache_contract.py` | Create | Layer 3: Pool cache structure, TTL contracts |
| `tests/test_music_pool_cache_integration.py` | Create | Layer 4: Pool hit/miss/rebuild/supplemental/random selection |
| `test.sh` | Modify | Add new test files to Layer 3 and Layer 4 |

---

## Task 1: CachedSong + CachedMusicPool dataclasses

**Files:**
- Modify: `src/services/music_service.py` (after existing imports, before `NeteaseMusicClient`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_music_pool_cache_contract.py
"""音乐混合缓存池契约测试 (Layer 3)"""

import pytest


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_contract.py -v`
Expected: FAIL with "ImportError: cannot import name 'CachedSong'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/services/music_service.py — insert after existing imports, before NeteaseMusicClient class

from dataclasses import dataclass, field


@dataclass
class CachedSong:
    """已验证URL的歌曲缓存项。"""
    id: int
    name: str
    artists: List[str]
    album: str
    duration: int
    url: str
    url_expires_at: float
    verified_at: float


@dataclass
class CachedMusicPool:
    """音乐缓存池。"""
    analysis: Dict[str, Any]
    verified_songs: List[CachedSong]
    created_at: float
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_contract.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/luicy/AI/story2
git add tests/test_music_pool_cache_contract.py src/services/music_service.py
git commit -m "feat(music): add CachedSong and CachedMusicPool dataclasses

- CachedSong: verified song with URL and expiration tracking
- CachedMusicPool: cache pool with analysis + verified songs list

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: MusicService pool cache class variables

**Files:**
- Modify: `src/services/music_service.py` (in MusicService class, after _analysis_cache)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_music_pool_cache_contract.py — append to existing file


class TestMusicServicePoolCacheContract:
    """验证 MusicService 缓存池类变量契约。"""

    def test_pool_cache_is_class_variable(self):
        """_pool_cache 必须是类级变量，跨实例共享。"""
        from src.services.music_service import MusicService

        assert "_pool_cache" in MusicService.__dict__, (
            "_pool_cache 必须是类级变量，确保跨实例缓存共享"
        )

    def test_pool_cache_ttl_value(self):
        """POOL_CACHE_TTL 应为 3600 秒（1 小时）。"""
        from src.services.music_service import MusicService

        assert MusicService.POOL_CACHE_TTL == 3600, (
            "POOL_CACHE_TTL 必须为 3600 秒（1 小时）"
        )

    def test_pool_cache_entry_structure(self):
        """缓存项应为 (CachedMusicPool, timestamp) 元组。"""
        from src.services.music_service import MusicService, CachedMusicPool, CachedSong
        import time

        pool = CachedMusicPool(
            analysis={"mood": "悲伤"},
            verified_songs=[
                CachedSong(
                    id=1001, name="测试", artists=["A"], album="X",
                    duration=1000, url="https://cdn.example.com/song.mp3",
                    url_expires_at=time.time() + 480, verified_at=time.time(),
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_contract.py::TestMusicServicePoolCacheContract -v`
Expected: FAIL with "AttributeError: type object 'MusicService' has no attribute '_pool_cache'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/services/music_service.py — in MusicService class, after _analysis_cache

class MusicService:
    """音乐服务：基于故事内容推荐音乐"""

    # ★ 缓存：基于故事文本 hash 缓存分析结果，避免重复 AI 调用
    _analysis_cache: Dict[str, tuple[Dict[str, Any], float]] = {}
    _CACHE_TTL = 3600  # 1 小时

    # ★ 缓存池：基于故事文本 hash 缓存已验证 URL 的歌曲池
    _pool_cache: Dict[str, tuple[CachedMusicPool, float]] = {}
    POOL_CACHE_TTL = 3600  # 1 小时（池整体重建）
    POOL_TARGET_SIZE = 25  # 目标池大小
    POOL_MIN_SIZE = 20     # 最小池大小（低于此值触发补充搜索）
    POOL_RETURN_MIN = 5    # 最少返回歌曲数
    POOL_RETURN_MAX = 8    # 最多返回歌曲数
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_contract.py::TestMusicServicePoolCacheContract -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/luicy/AI/story2
git add tests/test_music_pool_cache_contract.py src/services/music_service.py
git commit -m "feat(music): add MusicService pool cache class variables

- _pool_cache: class-level dict keyed by story_hash
- POOL_CACHE_TTL: 3600s pool rebuild interval
- POOL_TARGET_SIZE: 25 verified songs
- POOL_RETURN_MIN/MAX: 5-8 songs per request

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: _random_select_songs helper

**Files:**
- Modify: `src/services/music_service.py` (add method to MusicService)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_music_pool_cache_integration.py — create new file
"""音乐混合缓存池集成测试 (Layer 4)

验证缓存池的完整行为：命中、miss、随机选择、URL刷新等。
"""

import random
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_integration.py::TestRandomSelectSongs -v`
Expected: FAIL with "AttributeError: 'MusicService' object has no attribute '_random_select_songs'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/services/music_service.py — add method to MusicService class

    def _random_select_songs(self, pool: CachedMusicPool) -> List[CachedSong]:
        """从缓存池中随机选择 5-8 首歌曲。

        Args:
            pool: 缓存池

        Returns:
            随机选择的歌曲列表（5-8首，不重复）
        """
        songs = pool.verified_songs
        count = len(songs)

        if count <= self.POOL_RETURN_MIN:
            return songs[:]

        select_count = random.randint(self.POOL_RETURN_MIN, min(self.POOL_RETURN_MAX, count))
        selected = random.sample(songs, select_count)
        return selected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_integration.py::TestRandomSelectSongs -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/luicy/AI/story2
git add tests/test_music_pool_cache_integration.py src/services/music_service.py
git commit -m "feat(music): add _random_select_songs helper

- Returns 5-8 random songs from pool
- Returns all if pool has <5 songs
- Ensures no duplicates, all have URLs

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: _get_or_build_pool helper

**Files:**
- Modify: `src/services/music_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_music_pool_cache_integration.py — append

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
        story_hash = "test_hit"

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

        pool = await service._get_or_build_pool("test_hit", refresh=False)

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
        story_hash = "test_refresh"

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

        # Mock AI analysis — 不应该被调用
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

        pool = await service._get_or_build_pool("test_refresh", refresh=True)

        assert pool.analysis["mood"] == "悲伤"
        service._analyze_story_mood.assert_not_called()
        assert len(pool.verified_songs) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_integration.py::TestGetOrBuildPool -v`
Expected: FAIL with "AttributeError: 'MusicService' object has no attribute '_get_or_build_pool'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/services/music_service.py — add method to MusicService class (after _story_hash, before analyze_story_for_music)

    async def _get_or_build_pool(
        self,
        story_text: str,
        refresh: bool = False,
        character_settings: Optional[Dict] = None,
    ) -> CachedMusicPool:
        """获取或构建缓存池。

        Args:
            story_text: 故事文本
            refresh: 是否刷新（复用分析，重新搜索）
            character_settings: 角色设定

        Returns:
            缓存池
        """
        story_hash = self._story_hash(story_text)
        now = time.time()

        # 检查缓存
        if not refresh:
            cached = self._pool_cache.get(story_hash)
            if cached:
                pool, cached_at = cached
                if now - cached_at < self.POOL_CACHE_TTL:
                    logger.info(
                        f"[MusicPool] 命中缓存池: hash={story_hash[:8]}, "
                        f"age={int(now - cached_at)}s, songs={len(pool.verified_songs)}"
                    )
                    return pool
                else:
                    logger.info(f"[MusicPool] 缓存池过期: hash={story_hash[:8]}")

        # 需要构建/重建池
        logger.info(f"[MusicPool] 构建缓存池: hash={story_hash[:8]}, refresh={refresh}")

        # 获取/复用 AI 分析结果
        if refresh:
            cached_analysis = self._analysis_cache.get(story_hash)
            if cached_analysis:
                analysis, _ = cached_analysis
                logger.info(f"[MusicPool] 刷新: 复用缓存分析")
            else:
                analysis = await self._analyze_story_mood(story_text, character_settings)
                self._analysis_cache[story_hash] = (analysis, now)
        else:
            analysis = await self._analyze_story_mood(story_text, character_settings)
            self._analysis_cache[story_hash] = (analysis, now)

        # 构建搜索关键词
        search_keywords = self._build_search_keywords(analysis)

        # 刷新模式：打乱关键词顺序
        if refresh and len(search_keywords) > 3:
            shuffled = search_keywords[3:]
            random.shuffle(shuffled)
            search_keywords = search_keywords[:3] + shuffled
            logger.info("[MusicPool] 刷新: 关键词重排")

        # 搜索歌曲
        all_songs: List[Song] = []
        for keyword in search_keywords[:8]:
            songs = await self.music_client.search(keyword, limit=15)
            all_songs.extend(songs)

        # 去重
        seen_ids: set[int] = set()
        unique_songs: List[Song] = []
        for song in all_songs:
            if song.id not in seen_ids and len(unique_songs) < 30:
                seen_ids.add(song.id)
                unique_songs.append(song)

        # 补充搜索（如果太少）
        if len(unique_songs) < 15:
            generic_keywords = ["轻音乐", "纯音乐", "背景音乐", "流行", "经典", "华语"]
            for keyword in generic_keywords:
                if len(unique_songs) >= 15:
                    break
                songs = await self.music_client.search(keyword, limit=15)
                for song in songs:
                    if song.id not in seen_ids and len(unique_songs) < 30:
                        seen_ids.add(song.id)
                        unique_songs.append(song)

        # 批量获取 URL，只保留有 URL 的
        verified_songs: List[CachedSong] = []
        for song in unique_songs[:self.POOL_TARGET_SIZE]:
            try:
                url = await self.music_client.get_song_url(song.id)
                if url:
                    verified_songs.append(
                        CachedSong(
                            id=song.id,
                            name=song.name,
                            artists=song.artists,
                            album=song.album,
                            duration=song.duration,
                            url=url,
                            url_expires_at=now + NeteaseMusicClient.URL_CACHE_TTL,
                            verified_at=now,
                        )
                    )
            except Exception as e:
                logger.warning(f"[MusicPool] Failed to get URL for {song.id}: {e}")

        pool = CachedMusicPool(
            analysis=analysis,
            verified_songs=verified_songs,
            created_at=now,
        )
        self._pool_cache[story_hash] = (pool, now)

        logger.info(
            f"[MusicPool] 池构建完成: hash={story_hash[:8]}, "
            f"verified={len(verified_songs)}/{len(unique_songs)}"
        )
        return pool
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_integration.py::TestGetOrBuildPool -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/luicy/AI/story2
git add tests/test_music_pool_cache_integration.py src/services/music_service.py
git commit -m "feat(music): add _get_or_build_pool with caching

- Cache hit: return existing pool
- Cache miss: analyze + search + verify URLs + cache
- Refresh mode: reuse analysis, shuffle keywords, rebuild pool
- Pool target: 25 verified songs with URLs

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: _refresh_pool_urls helper

**Files:**
- Modify: `src/services/music_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_music_pool_cache_integration.py — append

class TestRefreshPoolUrls:
    """验证 _refresh_pool_urls 方法。"""

    @pytest.fixture(autouse=True)
    def _clear_caches(self):
        MusicService._analysis_cache.clear()
        MusicService._pool_cache.clear()

    async def test_refreshes_expired_urls(self):
        """过期的 URL 被重新获取。"""
        service = MusicService()
        now = time.time()

        # 创建有过期 URL 的池
        pool = CachedMusicPool(
            analysis={"mood": "悲伤"},
            verified_songs=[
                CachedSong(
                    id=5001, name="过期歌曲", artists=["F"], album="U",
                    duration=200000, url="https://old.example.com/5001.mp3",
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
                    id=6001, name="失败歌曲", artists=["G"], album="T",
                    duration=200000, url="https://old.example.com/6001.mp3",
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
                    id=7001, name="新鲜歌曲", artists=["H"], album="S",
                    duration=200000, url="https://fresh.example.com/7001.mp3",
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
                    id=8001, name="唯一歌曲", artists=["I"], album="R",
                    duration=200000, url="https://cdn.example.com/8001.mp3",
                    url_expires_at=now + 400,
                    verified_at=now,
                ),
            ],
            created_at=now,
        )

        # Mock search for supplemental
        service.music_client.search = AsyncMock(return_value=[
            Song(id=8002, name="补充歌曲", artists=["J"], album="Q", duration=210000),
        ])
        service.music_client.get_song_url = AsyncMock(
            return_value="https://cdn.example.com/8002.mp3"
        )

        await service._refresh_pool_urls(pool)

        service.music_client.search.assert_called()
        assert len(pool.verified_songs) >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_integration.py::TestRefreshPoolUrls -v`
Expected: FAIL with "AttributeError: 'MusicService' object has no attribute '_refresh_pool_urls'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/services/music_service.py — add method to MusicService class

    async def _refresh_pool_urls(self, pool: CachedMusicPool) -> None:
        """刷新池中过期 URL 的歌曲。

        过期的 URL 重新获取，获取失败的从池中移除。
        如果池中歌曲 <5 首，触发补充搜索。

        Args:
            pool: 缓存池
        """
        now = time.time()
        refreshed: List[CachedSong] = []
        removed = 0

        for song in pool.verified_songs:
            if song.url_expires_at < now:
                # URL 过期，重新获取
                try:
                    new_url = await self.music_client.get_song_url(song.id)
                    if new_url:
                        refreshed.append(
                            CachedSong(
                                id=song.id,
                                name=song.name,
                                artists=song.artists,
                                album=song.album,
                                duration=song.duration,
                                url=new_url,
                                url_expires_at=now + NeteaseMusicClient.URL_CACHE_TTL,
                                verified_at=now,
                            )
                        )
                        logger.info(f"[MusicPool] URL 刷新成功: {song.id}")
                    else:
                        removed += 1
                        logger.warning(f"[MusicPool] URL 刷新失败，移除: {song.id}")
                except Exception as e:
                    removed += 1
                    logger.warning(f"[MusicPool] URL 刷新异常，移除: {song.id}: {e}")
            else:
                refreshed.append(song)

        pool.verified_songs = refreshed

        # 补充搜索（如果太少）
        if len(refreshed) < 5:
            logger.info(f"[MusicPool] 歌曲不足({len(refreshed)}<5)，触发补充搜索")
            generic_keywords = ["轻音乐", "纯音乐", "背景音乐", "流行", "经典"]
            seen_ids = {s.id for s in refreshed}

            for keyword in generic_keywords:
                if len(refreshed) >= 5:
                    break
                try:
                    songs = await self.music_client.search(keyword, limit=10)
                    for song in songs:
                        if song.id in seen_ids or len(refreshed) >= 10:
                            continue
                        try:
                            url = await self.music_client.get_song_url(song.id)
                            if url:
                                refreshed.append(
                                    CachedSong(
                                        id=song.id,
                                        name=song.name,
                                        artists=song.artists,
                                        album=song.album,
                                        duration=song.duration,
                                        url=url,
                                        url_expires_at=now + NeteaseMusicClient.URL_CACHE_TTL,
                                        verified_at=now,
                                    )
                                )
                                seen_ids.add(song.id)
                        except Exception:
                            pass
                except Exception:
                    pass

            pool.verified_songs = refreshed

        if removed > 0:
            logger.info(f"[MusicPool] URL 刷新完成: 保留 {len(refreshed)} 首, 移除 {removed} 首")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_integration.py::TestRefreshPoolUrls -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/luicy/AI/story2
git add tests/test_music_pool_cache_integration.py src/services/music_service.py
git commit -m "feat(music): add _refresh_pool_urls helper

- Refreshes expired URLs in pool
- Removes songs when URL refresh fails
- Triggers supplemental search when <5 songs
- Keeps fresh URLs unchanged

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Wire up analyze_story_for_music

**Files:**
- Modify: `src/services/music_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_music_pool_cache_integration.py — append

class TestAnalyzeStoryForMusicWithPool:
    """验证 analyze_story_for_music 使用缓存池。"""

    @pytest.fixture(autouse=True)
    def _clear_caches(self):
        MusicService._analysis_cache.clear()
        MusicService._pool_cache.clear()

    async def test_returns_music_recommendation(self):
        """返回 MusicRecommendation 类型。"""
        service = MusicService()

        service._analyze_story_mood = AsyncMock(return_value={
            "mood": "悲伤",
            "keywords": ["伤感"],
            "scene_type": "叙事",
        })
        service.music_client.search = AsyncMock(return_value=[
            Song(id=9001, name="歌曲1", artists=["A"], album="X", duration=200000),
            Song(id=9002, name="歌曲2", artists=["B"], album="Y", duration=210000),
        ])
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

        service._analyze_story_mood = AsyncMock(return_value={
            "mood": "悲伤",
            "keywords": ["伤感"],
            "scene_type": "叙事",
        })

        # 生成足够多的歌曲
        songs = []
        for i in range(30):
            songs.append(
                Song(id=10000 + i, name=f"歌曲{i}", artists=[f"歌手{i}"],
                     album=f"专辑{i}", duration=200000 + i * 1000)
            )
        service.music_client.search = AsyncMock(return_value=songs)
        service.music_client.get_song_url = AsyncMock(
            side_effect=lambda song_id: f"https://cdn.example.com/{song_id}.mp3"
        )

        result = await service.analyze_story_for_music("一个悲伤的故事")

        assert 5 <= len(result.songs) <= 8, (
            f"返回 {len(result.songs)} 首，不在 5-8 范围内"
        )

    async def test_all_returned_songs_have_url(self):
        """返回的歌曲全部有 URL。"""
        service = MusicService()

        service._analyze_story_mood = AsyncMock(return_value={
            "mood": "悲伤",
            "keywords": ["伤感"],
            "scene_type": "叙事",
        })

        songs = []
        for i in range(30):
            songs.append(
                Song(id=11000 + i, name=f"歌曲{i}", artists=[f"歌手{i}"],
                     album=f"专辑{i}", duration=200000 + i * 1000)
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
        story_hash = service._story_hash("缓存测试故事")

        # 预填充缓存池
        pool = CachedMusicPool(
            analysis={"mood": "欢快"},
            verified_songs=[
                CachedSong(
                    id=12001, name="缓存歌曲", artists=["C"], album="Z",
                    duration=180000, url="https://cdn.example.com/12001.mp3",
                    url_expires_at=time.time() + 480, verified_at=time.time(),
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

        result = await service.analyze_story_for_music("缓存测试故事")

        assert result.mood == "欢快"
        service.music_client.search.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_integration.py::TestAnalyzeStoryForMusicWithPool -v`
Expected: FAIL — `analyze_story_for_music` still uses old implementation without pool

- [ ] **Step 3: Write minimal implementation**

Replace the existing `analyze_story_for_music` method with:

```python
# src/services/music_service.py — replace analyze_story_for_music method

    async def analyze_story_for_music(
        self,
        story_text: str,
        character_settings: Optional[Dict] = None,
        refresh: bool = False,
    ) -> MusicRecommendation:
        """分析故事内容，提取音乐搜索关键词，返回推荐歌曲。

        ★ 使用缓存池优化：
        - 首次：AI分析 + 搜索 + URL验证 → 缓存池
        - 后续：从缓存池中随机选择 5-8 首
        - 刷新：复用AI分析，打乱关键词重新搜索

        Args:
            story_text: 故事文本
            character_settings: 角色设定
            refresh: 是否刷新（复用缓存的 AI 分析结果，但重新搜索歌曲）

        Returns:
            音乐推荐结果（5-8首已验证URL的歌曲）
        """
        # 获取或构建缓存池
        pool = await self._get_or_build_pool(story_text, refresh, character_settings)

        # 刷新池中过期 URL
        await self._refresh_pool_urls(pool)

        # 从池中随机选择歌曲
        selected = self._random_select_songs(pool)

        logger.info(
            f"[MusicPool] 返回推荐: {len(selected)} 首, "
            f"pool={len(pool.verified_songs)} 首"
        )

        # 转换为 MusicRecommendation 格式
        return MusicRecommendation(
            keywords=self._build_search_keywords(pool.analysis),
            mood=pool.analysis.get("mood", "未知"),
            scene_type=pool.analysis.get("scene_type", "未知"),
            songs=[
                Song(
                    id=s.id,
                    name=s.name,
                    artists=s.artists,
                    album=s.album,
                    duration=s.duration,
                    url=s.url,
                )
                for s in selected
            ],
            environment=pool.analysis.get("environment"),
            story_style=pool.analysis.get("story_style"),
            music_style=pool.analysis.get("music_style"),
            instruments=pool.analysis.get("instruments"),
            pacing=pool.analysis.get("pacing"),
            time_weather=pool.analysis.get("time_weather"),
            description=pool.analysis.get("description"),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/luicy/AI/story2 && python3 -m pytest tests/test_music_pool_cache_integration.py::TestAnalyzeStoryForMusicWithPool -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/luicy/AI/story2
git add tests/test_music_pool_cache_integration.py src/services/music_service.py
git commit -m "feat(music): wire up analyze_story_for_music with pool cache

- Uses _get_or_build_pool for cache hit/miss
- Refreshes expired URLs before returning
- Randomly selects 5-8 songs from pool
- All returned songs have verified URLs

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Update test.sh

**Files:**
- Modify: `test.sh`

- [ ] **Step 1: Find the lines to modify**

Run: `grep -n "test_music" test.sh`

- [ ] **Step 2: Modify test.sh**

Add `tests/test_music_pool_cache_contract.py` to Layer 3 (contract tests) and `tests/test_music_pool_cache_integration.py` to Layer 4 (DB integration tests).

Find the existing lines:
```bash
python3 -m pytest tests/test_api_contract.py ... tests/test_music_service_url_contract.py ... -v
```
Add `tests/test_music_pool_cache_contract.py` to this line.

Find:
```bash
python3 -m pytest tests/test_integration_real_db.py ... tests/test_music_cache_integration.py ... -v
```
Add `tests/test_music_pool_cache_integration.py` to this line.

- [ ] **Step 3: Verify test.sh syntax**

Run: `bash -n test.sh`
Expected: No output (syntax OK)

- [ ] **Step 4: Run the new test layers**

Run:
```bash
cd /Users/luicy/AI/story2
python3 -m pytest tests/test_music_pool_cache_contract.py tests/test_music_pool_cache_integration.py -v
```
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/luicy/AI/story2
git add test.sh
git commit -m "ci: add music pool cache tests to test.sh

- Layer 3: test_music_pool_cache_contract.py
- Layer 4: test_music_pool_cache_integration.py

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Run full test suite

- [ ] **Step 1: Run all music-related tests**

```bash
cd /Users/luicy/AI/story2
python3 -m pytest tests/test_music_*.py -v
```
Expected: All PASS (no regressions in existing tests)

- [ ] **Step 2: Run pre-commit**

```bash
cd /Users/luicy/AI/story2
git add -A
git commit -m "feat(music): hybrid cache pool for music recommendations

- CachedSong + CachedMusicPool dataclasses
- MusicService._pool_cache with 1h TTL
- _get_or_build_pool: cache hit/miss/rebuild/refresh
- _refresh_pool_urls: expired URL refresh + supplemental search
- _random_select_songs: returns 5-8 unique songs from pool
- analyze_story_for_music: returns only verified songs with URLs

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

Expected: Pre-commit passes (mypy, isort, flake8, jest, coverage)

- [ ] **Step 3: Push and deploy**

```bash
cd /Users/luicy/AI/story2
git push origin main

# Deploy to ECS
sshpass -p 'maxminicherry@2026' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@47.250.162.194 "cd /opt/story2 && git pull origin main && docker compose -f docker-compose.ecs.yml up -d --build backend"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] CachedSong / CachedMusicPool dataclasses → Task 1
- [x] MusicService pool cache class variables → Task 2
- [x] _random_select_songs (5-8 unique songs) → Task 3
- [x] _get_or_build_pool (cache hit/miss/rebuild/refresh) → Task 4
- [x] _refresh_pool_urls (expired URL refresh + supplemental) → Task 5
- [x] analyze_story_for_music wired to pool → Task 6
- [x] test.sh updated → Task 7
- [x] Full test suite + deploy → Task 8

**Placeholder scan:** No TBD, TODO, or vague steps found.

**Type consistency:**
- `CachedSong` fields match usage in `_get_or_build_pool` and `_refresh_pool_urls`
- `CachedMusicPool` fields match usage throughout
- `MusicRecommendation` return type preserved in `analyze_story_for_music`
- `Song` type used for external interface compatibility

**No gaps found.**
