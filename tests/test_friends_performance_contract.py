"""契约测试：好友系统性能优化。

验证：
1. 后端好友查询使用批量加载避免 N+1
2. 前端好友列表有缓存机制
"""

import os


def test_friends_api_uses_joined_loading():
    """后端好友查询应使用 joinedload 或 selectinload 避免 N+1。"""
    user_manager_path = "src/database/user_manager.py"
    assert os.path.exists(user_manager_path), f"{user_manager_path} 不存在"

    with open(user_manager_path, "r") as f:
        content = f.read()

    # 应有批量加载策略，而非逐个查询
    has_optimization = any(
        kw in content
        for kw in [
            "joinedload",
            "selectinload",
            "subqueryload",
            "in_(",
            "IN (",
        ]
    )
    assert has_optimization, (
        "好友查询缺少批量加载优化（joinedload/selectinload/in_）—— "
        "当前 get_friends 对每个好友逐条查询，存在 N+1 问题"
    )


def test_friends_store_has_cache_mechanism():
    """useUserStore 应有好友列表缓存机制。"""
    store_path = "frontend/src/stores/useUserStore.ts"
    assert os.path.exists(store_path), f"{store_path} 不存在"

    with open(store_path, "r") as f:
        content = f.read()

    assert any(
        kw in content
        for kw in [
            "friendsCacheTime",
            "FRIENDS_CACHE_TTL",
            "lastFriendsRefresh",
        ]
    ), "useUserStore 缺少好友列表缓存机制（需要缓存时间戳字段）"


def test_friends_store_checks_cache_before_fetch():
    """fetchFriends 应在请求前检查缓存有效性。"""
    store_path = "frontend/src/stores/useUserStore.ts"
    assert os.path.exists(store_path), f"{store_path} 不存在"

    with open(store_path, "r") as f:
        content = f.read()

    assert (
        "Date.now()" in content
    ), "fetchFriends 缺少缓存时间检查——应使用 Date.now() 判断缓存是否过期"
