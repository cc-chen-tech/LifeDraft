"""Image ThreadPoolExecutor lifecycle contract tests.

验证图像服务模块中的线程池可以正确关闭。
B-02: 全局 ThreadPoolExecutor shutdown 后不应立即重新创建，避免资源泄漏。
"""

from concurrent.futures import ThreadPoolExecutor

from src.services import image_service


class TestImageThreadPoolLifecycle:
    """图像服务线程池生命周期契约测试"""

    def test_get_image_thread_pool_returns_thread_pool_executor(self):
        """get_image_thread_pool() 必须返回 ThreadPoolExecutor 实例"""
        pool = image_service.get_image_thread_pool()
        assert isinstance(pool, ThreadPoolExecutor)

    def test_shutdown_image_thread_pool_creates_new_pool_on_next_get(self):
        """shutdown_image_thread_pool() 关闭旧池；下次 get 时创建新实例"""
        pool = image_service.get_image_thread_pool()
        image_service.shutdown_image_thread_pool()
        # shutdown 后 get 应返回全新实例
        new_pool = image_service.get_image_thread_pool()
        assert new_pool is not pool
        assert isinstance(new_pool, ThreadPoolExecutor)

    def test_shutdown_image_thread_pool_is_idempotent(self):
        """多次调用 shutdown 不应报错"""
        image_service.shutdown_image_thread_pool()
        image_service.shutdown_image_thread_pool()
        pool = image_service.get_image_thread_pool()
        assert isinstance(pool, ThreadPoolExecutor)
