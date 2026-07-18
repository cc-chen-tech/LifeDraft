"""SSE ThreadPoolExecutor lifecycle contract tests.

验证 SSE 辅助模块中的线程池可以正确关闭和重新创建。
B-01: 全局 ThreadPoolExecutor 必须有 shutdown 机制以防止资源泄漏。
"""

from concurrent.futures import ThreadPoolExecutor

from src.api.routers.gameplay import sse_helpers


class TestSSEThreadPoolLifecycle:
    """SSE 线程池生命周期契约测试"""

    def test_get_sse_thread_pool_returns_thread_pool_executor(self):
        """get_sse_thread_pool() 必须返回 ThreadPoolExecutor 实例"""
        pool = sse_helpers.get_sse_thread_pool()
        assert isinstance(pool, ThreadPoolExecutor)

    def test_shutdown_sse_thread_pool_creates_new_pool(self):
        """shutdown_sse_thread_pool() 后应能获取新的线程池"""
        pool = sse_helpers.get_sse_thread_pool()
        sse_helpers.shutdown_sse_thread_pool()
        new_pool = sse_helpers.get_sse_thread_pool()
        assert new_pool is not pool
        assert isinstance(new_pool, ThreadPoolExecutor)

    def test_shutdown_sse_thread_pool_is_idempotent(self):
        """多次调用 shutdown 不应报错"""
        sse_helpers.shutdown_sse_thread_pool()
        sse_helpers.shutdown_sse_thread_pool()
        pool = sse_helpers.get_sse_thread_pool()
        assert isinstance(pool, ThreadPoolExecutor)

    def test_background_media_pool_is_separate_from_story_pool(self):
        """Slow media jobs must not occupy the story-generation worker pool."""
        story_pool = sse_helpers.get_sse_thread_pool()
        background_pool = sse_helpers.get_background_thread_pool()

        assert isinstance(background_pool, ThreadPoolExecutor)
        assert background_pool is not story_pool
        assert background_pool._max_workers < story_pool._max_workers
