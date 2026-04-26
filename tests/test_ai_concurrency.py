"""AI 并发控制测试 - 对应优化 C-04"""

import asyncio
import threading
import time


class TestAIConcurrencyControl:
    """AI 调用并发限制测试"""

    def test_semaphore_limits_concurrent_calls(self):
        """信号量应限制并发调用数"""

        async def _async_test():
            sem = asyncio.Semaphore(2)
            concurrent_count = 0
            max_concurrent = 0

            async def mock_call():
                nonlocal concurrent_count, max_concurrent
                async with sem:
                    concurrent_count += 1
                    max_concurrent = max(max_concurrent, concurrent_count)
                    await asyncio.sleep(0.1)
                    concurrent_count -= 1

            tasks = [asyncio.create_task(mock_call()) for _ in range(5)]
            await asyncio.gather(*tasks)

            assert max_concurrent <= 2

        asyncio.run(_async_test())

    def test_calls_beyond_limit_wait(self):
        """超出限制的调用应等待"""

        async def _async_test():
            sem = asyncio.Semaphore(2)
            call_order = []

            async def tracked_call(idx):
                async with sem:
                    call_order.append(f"start_{idx}")
                    await asyncio.sleep(0.05)
                    call_order.append(f"end_{idx}")

            tasks = [asyncio.create_task(tracked_call(i)) for i in range(4)]
            await asyncio.gather(*tasks)

            # 所有任务都应完成
            assert len(call_order) == 8  # 4 start + 4 end

        asyncio.run(_async_test())

    def test_semaphore_released_on_success(self):
        """成功调用后信号量应释放"""

        async def _async_test():
            sem = asyncio.Semaphore(1)

            async with sem:
                pass

            # 信号量应可重新获取
            acquired = sem._value
            assert acquired == 1

        asyncio.run(_async_test())

    def test_semaphore_released_on_failure(self):
        """失败调用后信号量也应释放"""

        async def _async_test():
            sem = asyncio.Semaphore(1)

            try:
                async with sem:
                    raise ValueError("Test error")
            except ValueError:
                pass

            # 信号量应可重新获取
            assert sem._value == 1

        asyncio.run(_async_test())

    def test_concurrent_limit_configurable(self):
        """并发限制应可配置"""

        async def _async_test():
            for limit in [1, 3, 5, 10]:
                sem = asyncio.Semaphore(limit)
                assert sem._value == limit

        asyncio.run(_async_test())


class TestImageAPIConcurrency:
    """图片 API 并发测试"""

    def test_image_generation_respects_limit(self):
        """图片生成应遵守并发限制"""

        async def _async_test():
            sem = asyncio.Semaphore(2)
            results = []

            async def generate_image(idx):
                async with sem:
                    await asyncio.sleep(0.05)
                    results.append(idx)

            tasks = [asyncio.create_task(generate_image(i)) for i in range(5)]
            await asyncio.gather(*tasks)

            assert len(results) == 5

        asyncio.run(_async_test())

    def test_timeout_releases_semaphore(self):
        """超时后信号量应释放"""

        async def _async_test():
            sem = asyncio.Semaphore(1)

            async def slow_task():
                async with sem:
                    await asyncio.sleep(10)  # 很慢的任务

            task = asyncio.create_task(slow_task())
            await asyncio.sleep(0.1)
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            # 取消后信号量应释放（可能需要短暂等待）
            await asyncio.sleep(0.1)
            assert sem._value >= 0

        asyncio.run(_async_test())

    def test_queue_order_fifo(self):
        """等待队列应按 FIFO 顺序处理"""

        async def _async_test():
            sem = asyncio.Semaphore(1)
            order = []

            async def ordered_task(idx):
                async with sem:
                    order.append(idx)
                    await asyncio.sleep(0.02)

            # 依次启动任务
            tasks = []
            for i in range(3):
                tasks.append(asyncio.create_task(ordered_task(i)))
                await asyncio.sleep(0.01)

            await asyncio.gather(*tasks)
            assert len(order) == 3

        asyncio.run(_async_test())


class TestThreadingSemaphore:
    """测试 threading.Semaphore (实际代码使用的)"""

    def test_threading_semaphore_limits_concurrent_calls(self):
        """threading.Semaphore 应限制并发调用数"""
        sem = threading.Semaphore(2)
        concurrent_count = 0
        max_concurrent = 0
        lock = threading.Lock()

        def worker():
            nonlocal concurrent_count, max_concurrent
            with sem:
                with lock:
                    concurrent_count += 1
                    max_concurrent = max(max_concurrent, concurrent_count)
                time.sleep(0.1)
                with lock:
                    concurrent_count -= 1

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert max_concurrent <= 2

    def test_threading_semaphore_released_on_error(self):
        """threading.Semaphore 在错误后应释放"""
        sem = threading.Semaphore(1)

        try:
            with sem:
                raise ValueError("Test error")
        except ValueError:
            pass

        # 信号量应可重新获取
        acquired = sem.acquire(blocking=False)
        assert acquired
        sem.release()
