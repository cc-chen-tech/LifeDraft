"""Retirement boundary for historical friendship persistence helpers.

The database helper is intentionally retained for historical data compatibility,
but no frontend cache or runtime API is allowed to remain.
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


def test_retired_friends_store_has_no_cache_or_fetch_action():
    """The auth store must not retain dormant friend fetching behavior."""
    store_path = "frontend/src/stores/useUserStore.ts"
    assert os.path.exists(store_path), f"{store_path} 不存在"

    with open(store_path, "r") as f:
        content = f.read()

    assert "FRIENDS_CACHE_TTL" not in content
    assert "lastFriendsRefresh" not in content
    assert "fetchFriends" not in content


def test_retired_friends_router_is_not_registered():
    """The historical helper must not make the product API reachable."""
    main_path = "src/api/main.py"
    with open(main_path, "r") as f:
        content = f.read()

    assert "friends.router" not in content
    assert 'prefix="/api/friends"' not in content
