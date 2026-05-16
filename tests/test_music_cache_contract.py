"""音乐服务缓存契约测试 (Layer 3)

验证 NeteaseMusicClient 缓存行为的接口契约。
"""

import asyncio
import time

import pytest


class TestMusicCacheTTLContract:
    """验证缓存 TTL 常量契约。"""

    def test_url_cache_ttl_value(self):
        """URL_CACHE_TTL 应为 480 秒（8 分钟）。

        ★ 修复：从 1200s (20分钟) 降到 480s (8分钟)
        网易云 CDN URL 通常只有 5-10 分钟有效期
        20 分钟导致缓存未过期但 URL 已失效（403）
        8 分钟在 CDN 典型有效期内，减少 403 概率
        """
        from src.services.music_service import NeteaseMusicClient

        assert NeteaseMusicClient.URL_CACHE_TTL == 480, (
            "URL_CACHE_TTL 必须为 480 秒（8 分钟），"
            "确保在网易云 CDN URL 典型有效期 (5-10分钟) 内"
        )

    def test_url_cache_is_class_variable(self):
        """_url_cache 必须是类级变量，跨实例共享。"""
        from src.services.music_service import NeteaseMusicClient

        # 验证是类属性而非实例属性
        assert (
            "_url_cache" in NeteaseMusicClient.__dict__
        ), "_url_cache 必须是类级变量，确保跨实例缓存共享"

    def test_cache_entry_structure(self):
        """缓存项应为 (url, expire_timestamp) 元组。"""
        from src.services.music_service import NeteaseMusicClient

        # 手动插入一个缓存项
        test_url = "https://test.example.com/song.mp3"
        expire_ts = time.time() + 1200
        NeteaseMusicClient._url_cache[99999] = (test_url, expire_ts)

        cached = NeteaseMusicClient._url_cache.get(99999)
        assert cached is not None
        assert isinstance(cached, tuple), "缓存项必须是元组"
        assert len(cached) == 2, "缓存项必须是 (url, expire_timestamp) 二元组"
        assert isinstance(cached[0], str), "缓存项第一个元素必须是 URL 字符串"
        assert isinstance(cached[1], float), "缓存项第二个元素必须是过期时间戳（float）"

        # 清理
        del NeteaseMusicClient._url_cache[99999]


class TestMusicCacheHitContract:
    """验证缓存命中行为契约。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """每个测试前清除缓存。"""
        from src.services.music_service import NeteaseMusicClient

        NeteaseMusicClient._url_cache.clear()

    def test_cache_hit_returns_url_without_api_call(self):
        """缓存命中时应直接返回 URL，不触发网络请求。"""
        from src.services.music_service import NeteaseMusicClient

        client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")
        # Mock httpx client
        mock_client = type(
            "MockClient",
            (),
            {"get": lambda *args, **kwargs: pytest.fail("缓存命中时不应调用 API")},
        )()
        client.client = mock_client

        # 预填充缓存
        test_url = "https://cdn.example.com/song.mp3"
        NeteaseMusicClient._url_cache[12345] = (test_url, time.time() + 1200)

        # 验证缓存命中直接返回
        result = asyncio.run(client.get_song_url(12345))
        assert result == test_url, "缓存命中应直接返回缓存的 URL"

    def test_cache_expired_deletes_entry(self):
        """缓存过期时应删除条目并返回 None（触发重新获取）。"""
        from src.services.music_service import NeteaseMusicClient

        client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")

        # 预填充过期缓存
        test_url = "https://cdn.example.com/song.mp3"
        NeteaseMusicClient._url_cache[12346] = (test_url, time.time() - 1)

        # 验证过期缓存被删除
        assert 12346 in NeteaseMusicClient._url_cache
        asyncio.run(client.get_song_url(12346))
        assert 12346 not in NeteaseMusicClient._url_cache, "过期缓存条目必须被删除"

    def test_cache_miss_triggers_api_call(self):
        """缓存未命中时应触发 API 调用。"""
        from src.services.music_service import NeteaseMusicClient

        client = NeteaseMusicClient(base_url="http://127.0.0.1:3000")

        api_called = False

        async def mock_get(*args, **kwargs):
            nonlocal api_called
            api_called = True

            # 返回模拟响应
            class MockResponse:
                status_code = 200

                def json(self):
                    return {
                        "code": 200,
                        "data": [{"url": "https://cdn.example.com/new.mp3"}],
                    }

                def raise_for_status(self):
                    pass

            return MockResponse()

        client.client = type("MockClient", (), {"get": mock_get})()

        result = asyncio.run(client.get_song_url(12347))
        assert api_called, "缓存未命中时必须触发 API 调用"
        assert result == "https://cdn.example.com/new.mp3"


class TestMusicCacheTTLRiskContract:
    """验证缓存 TTL 与 CDN URL 实际有效期的风险契约。

    ★ 修复后：TTL (480s = 8分钟) 在网易云 CDN URL 典型有效期 (300-600s) 范围内
    既不会过于频繁失效，也不会在 URL 已过期时仍返回缓存。
    """

    def test_cache_ttl_within_cdn_typical_lifetime(self):
        """TTL 应在 CDN URL 典型有效期内。

        修复前：TTL (1200s) > CDN 最大有效期 (600s)，导致 403
        修复后：TTL (480s) 在 CDN 典型有效期 (300-600s) 范围内
        """
        from src.services.music_service import NeteaseMusicClient

        CDN_TYPICAL_LIFETIME_MIN = 300  # 5 分钟
        CDN_TYPICAL_LIFETIME_MAX = 600  # 10 分钟

        ttl = NeteaseMusicClient.URL_CACHE_TTL

        # TTL 应在 CDN 典型有效期内
        assert CDN_TYPICAL_LIFETIME_MIN <= ttl <= CDN_TYPICAL_LIFETIME_MAX, (
            f"TTL ({ttl}s) 应在 CDN 典型有效期 "
            f"[{CDN_TYPICAL_LIFETIME_MIN}s, {CDN_TYPICAL_LIFETIME_MAX}s] 范围内"
        )
