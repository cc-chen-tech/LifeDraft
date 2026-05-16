"""Music Service Health Check Contract Tests.

验证 NeteaseMusicClient 的健康检查机制：
- check_availability 缓存逻辑
- _available 状态流转
- search 在不可用时的短路行为
- HEALTH_CHECK_TIMEOUT 常量契约
"""

import asyncio


class TestMusicClientInitialization:
    """测试客户端初始化状态契约"""

    def test_health_check_timeout_is_3_seconds(self):
        """快速失败超时应为 3 秒"""
        from src.services.music_service import NeteaseMusicClient

        assert NeteaseMusicClient.HEALTH_CHECK_TIMEOUT == 3.0

    def test_url_cache_ttl_is_8_minutes(self):
        """URL 缓存 TTL 应为 480 秒"""
        from src.services.music_service import NeteaseMusicClient

        assert NeteaseMusicClient.URL_CACHE_TTL == 480

    def test_available_is_none_on_init(self):
        """初始化时 _available 为 None（未检查状态）"""
        from src.services.music_service import NeteaseMusicClient

        client = NeteaseMusicClient()
        assert client._available is None, "初始状态应为 None（未检查）"

    def test_base_url_default_is_music_api(self):
        """默认 base_url 指向 music-api 容器"""
        from src.services.music_service import NeteaseMusicClient

        client = NeteaseMusicClient()
        assert "music-api" in client.base_url or "3001" in client.base_url


class TestHealthCheckAvailabilityCache:
    """测试 check_availability 缓存逻辑（不发起真实 HTTP 请求）"""

    def test_cached_true_returned_without_http_call(self):
        """_available=True 时直接返回 True，不发起 HTTP 请求"""
        from src.services.music_service import NeteaseMusicClient

        client = NeteaseMusicClient()
        client._available = True
        result = asyncio.run(client.check_availability())
        assert result is True, "已缓存为 True 时应直接返回"

    def test_cached_false_returned_without_http_call(self):
        """_available=False 时直接返回 False，不发起 HTTP 请求"""
        from src.services.music_service import NeteaseMusicClient

        client = NeteaseMusicClient()
        client._available = False
        result = asyncio.run(client.check_availability())
        assert result is False, "已缓存为 False 时应直接返回"


class TestSearchShortCircuit:
    """测试不可用时的搜索短路行为"""

    def test_search_returns_empty_when_unavailable(self):
        """_available=False 时搜索直接返回空列表"""
        from src.services.music_service import NeteaseMusicClient

        client = NeteaseMusicClient()
        client._available = False
        result = asyncio.run(client.search("test"))
        assert result == [], "不可用时应返回空列表"
        assert isinstance(result, list)

    def test_search_returns_list_when_available_unknown(self):
        """_available=None 时正常尝试搜索"""
        from src.services.music_service import NeteaseMusicClient

        client = NeteaseMusicClient()
        client._available = None
        # 会发起真实 HTTP 请求，可能成功也可能超时
        # 这里只验证返回类型一致
        result = asyncio.run(client.search("test"))
        assert isinstance(result, list), "搜索始终应返回列表"


class TestHealthCheckContract:
    """测试 check_availability 返回值契约"""

    def test_check_availability_returns_bool(self):
        """check_availability 始终返回 bool"""
        from src.services.music_service import NeteaseMusicClient

        client = NeteaseMusicClient()
        # 强制设为已知状态以避免 HTTP 调用
        client._available = True
        result = asyncio.run(client.check_availability())
        assert isinstance(result, bool)

    def test_check_availability_is_async(self):
        """check_availability 是异步方法"""
        from src.services.music_service import NeteaseMusicClient

        assert asyncio.iscoroutinefunction(NeteaseMusicClient.check_availability), "应为 async 方法"
