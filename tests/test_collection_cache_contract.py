"""契约测试：收集面板缓存机制。"""


def test_collection_store_has_cache_mechanism():
    """useCollectionStore 应有缓存相关代码（lastFetchTime 或 cacheExpiry）。"""
    with open("frontend/src/stores/useCollectionStore.ts", "r") as f:
        content = f.read()
    assert any(kw in content for kw in ["lastFetchTime", "cacheExpiry", "cacheTimestamp", "CACHE_TTL"]), \
        "useCollectionStore 缺少缓存机制"


def test_collection_store_checks_cache_before_fetch():
    """fetchCollection 应在请求前检查缓存有效性。"""
    with open("frontend/src/stores/useCollectionStore.ts", "r") as f:
        content = f.read()
    # 应有缓存时间检查逻辑
    assert "Date.now()" in content or "performance.now()" in content, \
        "fetchCollection 缺少缓存时间检查"


def test_collection_store_has_ttl_constant():
    """应定义缓存 TTL 常量。"""
    with open("frontend/src/stores/useCollectionStore.ts", "r") as f:
        content = f.read()
    assert "CACHE_TTL" in content or "CACHE_DURATION" in content or "30000" in content or "30 * 1000" in content, \
        "缺少缓存 TTL 常量定义"
