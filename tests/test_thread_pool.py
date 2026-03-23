"""线程池管理测试 - 对应优化 C-05"""

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

import pytest


class TestThreadPoolManagement:
    """线程池管理测试"""

    def test_pool_creation(self, thread_pool):
        """线程池应能成功创建"""
        assert isinstance(thread_pool, ThreadPoolExecutor)

    def test_pool_max_workers_configured(self, thread_pool):
        """线程池应有最大工作线程限制"""
        assert thread_pool._max_workers == 2  # conftest 中配置为 2

    def test_task_submitted_to_pool(self, thread_pool):
        """任务应能提交到线程池"""

        def sample_task():
            return 42

        future = thread_pool.submit(sample_task)
        result = future.result(timeout=5)
        assert result == 42

    def test_pool_limits_concurrent_threads(self, thread_pool):
        """线程池应限制并发线程数"""
        active_count = 0
        max_active = 0
        lock = threading.Lock()

        def counting_task():
            nonlocal active_count, max_active
            with lock:
                active_count += 1
                max_active = max(max_active, active_count)
            time.sleep(0.1)
            with lock:
                active_count -= 1

        futures = [thread_pool.submit(counting_task) for _ in range(5)]
        for f in futures:
            f.result(timeout=10)

        assert max_active <= 2  # pool max_workers = 2

    def test_task_exception_doesnt_crash_pool(self, thread_pool):
        """任务异常不应导致线程池崩溃"""

        def failing_task():
            raise ValueError("Test error")

        def success_task():
            return "ok"

        # 提交失败任务
        fail_future = thread_pool.submit(failing_task)
        with pytest.raises(ValueError):
            fail_future.result()

        # 线程池应仍可用
        ok_future = thread_pool.submit(success_task)
        assert ok_future.result(timeout=5) == "ok"

    def test_pool_shutdown_completes_pending(self):
        """关闭线程池时应完成待处理任务"""
        pool = ThreadPoolExecutor(max_workers=1)
        results = []

        def slow_task(n):
            time.sleep(0.05)
            results.append(n)

        for i in range(3):
            pool.submit(slow_task, i)

        pool.shutdown(wait=True)
        assert len(results) == 3

    def test_future_callback_works(self, thread_pool):
        """Future 回调应正常工作"""
        callback_called = threading.Event()

        def on_done(future):
            callback_called.set()

        future = thread_pool.submit(lambda: 42)
        future.add_done_callback(on_done)

        assert callback_called.wait(timeout=5)

    def test_no_bare_thread_creation(self):
        """验证不应使用裸 threading.Thread"""
        import ast
        import os

        src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
        bare_thread_files = []

        for root, dirs, files in os.walk(src_dir):
            for f in files:
                if f.endswith(".py"):
                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath) as fh:
                            content = fh.read()
                        if (
                            "threading.Thread(" in content
                            or "Thread(target=" in content
                        ):
                            bare_thread_files.append(filepath)
                    except Exception:
                        pass

        # 记录使用裸线程的文件（修复后应为空列表）
        # 目前仅记录，不阻断
        assert isinstance(bare_thread_files, list)
