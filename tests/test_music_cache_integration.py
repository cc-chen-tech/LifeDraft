"""音乐服务缓存集成测试 (Layer 4)

验证 NeteaseMusicClient 缓存的真实行为：命中、过期、403 刷新等。
"""

import asyncio
import time
from unittest.mock import MagicMock

import httpx
import pytest

from src.services.music_service import NeteaseMusicClient


class TestCacheHitAvoidsNetworkRequest:
    """验证缓存命中时避免网络请求。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """每个测试前清除缓存。"""
        NeteaseMusicClient._url_cache.clear()

    def test_cache_hit_no_api_call(self):
        """缓存命中时不应调用外部 API。"""
        client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")

        # 创建一个会失败的 mock（如果调用就会失败）
        client.client = MagicMock()
        client.client.get = MagicMock(side_effect=Exception("Should not be called when cache hits"))

        # 预填充有效缓存
        test_url = "https://cdn.example.com/cached.mp3"
        NeteaseMusicClient._url_cache[10001] = (test_url, time.time() + 1200)

        # 验证缓存命中直接返回，不调用 API
        result = asyncio.run(client.get_song_url(10001))
        assert result == test_url
        client.client.get.assert_not_called()

    def test_cache_expired_triggers_new_request(self):
        """缓存过期时应触发新的 API 请求。"""
        client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")

        api_called = False

        async def mock_get(*args, **kwargs):
            nonlocal api_called
            api_called = True
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json.return_value = {
                "code": 200,
                "data": [{"url": "https://cdn.example.com/fresh.mp3"}],
            }
            resp.raise_for_status.return_value = None
            return resp

        client.client = MagicMock()
        client.client.get = mock_get

        # 预填充过期缓存
        NeteaseMusicClient._url_cache[10002] = (
            "https://old.example.com/old.mp3",
            time.time() - 10,  # 已过期
        )

        result = asyncio.run(client.get_song_url(10002))

        assert api_called, "缓存过期时必须触发新的 API 请求"
        assert result == "https://cdn.example.com/fresh.mp3"

    def test_cache_miss_triggers_api_call(self):
        """缓存未命中时应触发 API 调用。"""
        client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")

        api_called = False

        async def mock_get(*args, **kwargs):
            nonlocal api_called
            api_called = True
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json.return_value = {
                "code": 200,
                "data": [{"url": "https://cdn.example.com/new.mp3"}],
            }
            resp.raise_for_status.return_value = None
            return resp

        client.client = MagicMock()
        client.client.get = mock_get

        result = asyncio.run(client.get_song_url(10003))

        assert api_called, "缓存未命中时必须触发 API 调用"
        assert result == "https://cdn.example.com/new.mp3"


class TestCacheExpiredDeletesEntry:
    """验证过期缓存条目被删除。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        NeteaseMusicClient._url_cache.clear()

    def test_expired_cache_entry_removed(self):
        """过期缓存条目在访问后应被删除并替换为新值。"""
        client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")

        # 预填充过期缓存
        old_url = "https://old.example.com/song.mp3"
        NeteaseMusicClient._url_cache[10004] = (
            old_url,
            time.time() - 1,
        )
        assert 10004 in NeteaseMusicClient._url_cache

        # Mock API 返回新 URL
        async def mock_get(*args, **kwargs):
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json.return_value = {
                "code": 200,
                "data": [{"url": "https://cdn.example.com/new.mp3"}],
            }
            resp.raise_for_status.return_value = None
            return resp

        client.client = MagicMock()
        client.client.get = mock_get

        result = asyncio.run(client.get_song_url(10004))

        # 验证过期缓存被替换为新值（不是旧值）
        assert result == "https://cdn.example.com/new.mp3", "过期缓存必须被新获取的 URL 替换"
        assert 10004 in NeteaseMusicClient._url_cache, "新获取的 URL 应被写入缓存"
        cached_url, cached_ts = NeteaseMusicClient._url_cache[10004]
        assert (
            cached_url == "https://cdn.example.com/new.mp3"
        ), "缓存中的 URL 必须是新获取的，不是过期的旧 URL"
        assert cached_ts > time.time(), "新缓存的过期时间必须在未来"

    def test_fresh_cache_entry_preserved(self):
        """未过期缓存条目应被保留。"""
        client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")

        # 预填充有效缓存
        NeteaseMusicClient._url_cache[10005] = (
            "https://cdn.example.com/fresh.mp3",
            time.time() + 600,  # 10 分钟后过期
        )

        # Mock 一个会失败的 client（如果调用就会失败）
        client.client = MagicMock()
        client.client.get = MagicMock(side_effect=Exception("Should not be called"))

        result = asyncio.run(client.get_song_url(10005))

        assert result == "https://cdn.example.com/fresh.mp3"
        assert 10005 in NeteaseMusicClient._url_cache, "有效缓存条目必须被保留"


class TestCacheClearedExternallyRefreshes:
    """验证缓存被外部清除后重新获取 URL。

    注意：真正的 403 处理逻辑在 music.py 路由层（流代理），
    这里测试 NeteaseMusicClient 层面的缓存行为：
    当外部代码（如 music.py）清除缓存后，再次请求应触发新 API 调用。
    """

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        NeteaseMusicClient._url_cache.clear()

    def test_external_cache_clear_triggers_refetch(self):
        """外部清除缓存后，再次请求应重新获取 URL。

        模拟 music.py 中 403 处理逻辑的行为：
        1. 缓存命中，返回旧 URL
        2. 外部检测到 403，清除缓存
        3. 再次请求，触发新 API 调用获取新 URL
        """
        client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")

        # 预填充缓存
        old_url = "https://cdn.example.com/old.mp3"
        NeteaseMusicClient._url_cache[10006] = (old_url, time.time() + 1200)

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json.return_value = {
                "code": 200,
                "data": [{"url": "https://cdn.example.com/refreshed.mp3"}],
            }
            resp.raise_for_status.return_value = None
            return resp

        client.client = MagicMock()
        client.client.get = mock_get

        # 步骤 1：缓存命中，直接返回旧 URL
        result = asyncio.run(client.get_song_url(10006))
        assert result == old_url
        assert call_count == 0, "缓存命中时不应调用 API"

        # 步骤 2：模拟外部清除缓存（如 music.py 中 403 时的行为）
        if 10006 in NeteaseMusicClient._url_cache:
            del NeteaseMusicClient._url_cache[10006]

        # 步骤 3：再次请求，应触发新 API 调用
        result = asyncio.run(client.get_song_url(10006))

        assert call_count == 1, "缓存清除后应触发新的 API 请求"
        assert result == "https://cdn.example.com/refreshed.mp3"


class TestCacheEntryWrittenAfterFetch:
    """验证获取后缓存条目被正确写入。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        NeteaseMusicClient._url_cache.clear()

    def test_new_url_cached_after_fetch(self):
        """新获取的 URL 应被写入缓存。"""
        client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")

        async def mock_get(*args, **kwargs):
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json.return_value = {
                "code": 200,
                "data": [{"url": "https://cdn.example.com/cached.mp3"}],
            }
            resp.raise_for_status.return_value = None
            return resp

        client.client = MagicMock()
        client.client.get = mock_get

        assert 10007 not in NeteaseMusicClient._url_cache

        result = asyncio.run(client.get_song_url(10007))

        assert result == "https://cdn.example.com/cached.mp3"
        assert 10007 in NeteaseMusicClient._url_cache, "新获取的 URL 必须被写入缓存"

        cached = NeteaseMusicClient._url_cache[10007]
        assert cached[0] == "https://cdn.example.com/cached.mp3"
        assert cached[1] > time.time(), "缓存过期时间必须在未来"


class TestCacheTTLConfiguration:
    """验证缓存 TTL 配置。"""

    def test_ttl_matches_constant(self):
        """实际缓存的过期时间应与 URL_CACHE_TTL 一致。"""
        from src.services.music_service import NeteaseMusicClient

        client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")

        async def mock_get(*args, **kwargs):
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json.return_value = {
                "code": 200,
                "data": [{"url": "https://cdn.example.com/test.mp3"}],
            }
            resp.raise_for_status.return_value = None
            return resp

        client.client = MagicMock()
        client.client.get = mock_get

        before = time.time()
        asyncio.run(client.get_song_url(10008))

        cached = NeteaseMusicClient._url_cache[10008]
        ttl = cached[1] - before

        assert (
            ttl >= NeteaseMusicClient.URL_CACHE_TTL - 1
        ), f"缓存 TTL ({ttl:.0f}s) 应接近 URL_CACHE_TTL ({NeteaseMusicClient.URL_CACHE_TTL}s)"

        # 清理
        del NeteaseMusicClient._url_cache[10008]
