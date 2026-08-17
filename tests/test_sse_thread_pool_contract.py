"""SSE ThreadPoolExecutor lifecycle contract tests.

验证 SSE 辅助模块中的线程池可以正确关闭和重新创建。
B-01: 全局 ThreadPoolExecutor 必须有 shutdown 机制以防止资源泄漏。
"""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from src.api.routers.gameplay import sse_helpers
import pytest

pytestmark = [pytest.mark.unit]



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
        assert background_pool._max_workers == 4
        assert story_pool._max_workers == 20

    def test_round_illustration_job_snapshots_current_state_before_queueing(self):
        """A delayed scene job must keep the event's original story and round identity."""
        player_state = SimpleNamespace(
            week=1,
            current_round=2,
            character_settings={"city": "Shanghai"},
            player_name="Chen Yue",
            world_model_data={"location": "studio"},
            established_facts=[{"fact": "budget spreadsheet"}],
        )
        game_loop = SimpleNamespace(player_state=player_state)
        event = SimpleNamespace(event_description="Chen Yue reviews the budget at dusk.")

        job = sse_helpers.build_round_illustration_job(game_loop, 41, event, "event")

        player_state.week = 2
        player_state.current_round = 0
        player_state.character_settings["city"] = "Beijing"
        event.event_description = "A later unrelated event"

        assert job.week == 1
        assert job.round_number == 2
        assert job.story_text == "Chen Yue reviews the budget at dusk."
        assert job.character_settings == {"city": "Shanghai"}
        assert job.world_model_data == {"location": "studio"}

    def test_permanent_shutdown_rejects_late_background_submission(self, monkeypatch):
        """A finishing story worker cannot recreate media workers during app shutdown."""
        monkeypatch.setattr(sse_helpers, "_background_jobs_enabled", True)
        sse_helpers.get_background_thread_pool()

        sse_helpers.shutdown_sse_thread_pool(wait=False, prevent_new_background_jobs=True)
        submitted = sse_helpers.submit_background_job("late-scene", lambda: None)

        assert submitted is False
        assert sse_helpers._background_thread_pool is None
