"""缓存管理测试 - 对应优化 H-07"""

import time

import pytest


class TestCacheManagement:
    """缓存 TTL 和大小限制测试"""

    def test_cache_respects_max_size(self, mock_cache_with_ttl):
        """缓存应遵守最大大小限制"""
        cache = mock_cache_with_ttl(max_size=3, ttl=3600)

        for i in range(5):
            cache.set(f"key_{i}", f"value_{i}")

        assert cache.size <= 3

    def test_cache_evicts_lru_entry(self, mock_cache_with_ttl):
        """满时应淘汰最近最少使用的条目"""
        cache = mock_cache_with_ttl(max_size=3, ttl=3600)

        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        # 访问 a 使其变为最近使用
        cache.get("a")

        # 插入新条目应淘汰 b（最近最少使用）
        cache.set("d", 4)

        assert cache.get("a") is not None  # 最近访问过
        assert cache.get("d") is not None  # 新插入
        assert cache.size <= 3

    def test_cache_ttl_expiration(self, mock_cache_with_ttl):
        """条目应在 TTL 后过期"""
        cache = mock_cache_with_ttl(max_size=10, ttl=0.1)  # 0.1秒 TTL

        cache.set("key", "value")
        assert cache.get("key") == "value"

        time.sleep(0.2)  # 等待过期
        assert cache.get("key") is None

    def test_expired_entry_returns_none(self, mock_cache_with_ttl):
        """过期条目应返回 None"""
        cache = mock_cache_with_ttl(max_size=10, ttl=0.05)
        cache.set("temp", "data")
        time.sleep(0.1)
        assert cache.get("temp") is None

    def test_cache_hit_updates_access_time(self, mock_cache_with_ttl):
        """缓存命中应更新访问时间"""
        cache = mock_cache_with_ttl(max_size=3, ttl=3600)

        cache.set("a", 1)
        time.sleep(0.01)
        cache.set("b", 2)
        time.sleep(0.01)

        # 访问 a 更新其访问时间
        cache.get("a")

        cache.set("c", 3)
        cache.set("d", 4)  # 应淘汰 b 而非 a

        assert cache.get("a") is not None

    def test_cache_size_after_eviction(self, mock_cache_with_ttl):
        """淘汰后大小应正确"""
        cache = mock_cache_with_ttl(max_size=2, ttl=3600)

        cache.set("x", 1)
        cache.set("y", 2)
        assert cache.size == 2

        cache.set("z", 3)  # 触发淘汰
        assert cache.size == 2

    def test_cache_delete(self, mock_cache_with_ttl):
        """手动删除应生效"""
        cache = mock_cache_with_ttl(max_size=10, ttl=3600)
        cache.set("key", "value")
        cache.delete("key")
        assert cache.get("key") is None
        assert cache.size == 0

    def test_cache_overwrite_same_key(self, mock_cache_with_ttl):
        """相同 key 应覆盖而非增加"""
        cache = mock_cache_with_ttl(max_size=2, ttl=3600)
        cache.set("key", "v1")
        cache.set("key", "v2")
        assert cache.get("key") == "v2"
        assert cache.size == 1
