"""实体识别任务管理单元测试

测试任务状态转换、进度计算、防重复启动等核心逻辑。
"""

from datetime import datetime, timedelta

import pytest

from src.services.entity_recognition_task import (EntityRecognitionTask,
                                                  TaskStatus, get_task_manager,
                                                  reset_task_manager)


class TestEntityRecognitionTask:
    """测试 EntityRecognitionTask 类"""

    def test_task_initialization(self):
        """测试任务初始化状态"""
        task = EntityRecognitionTask(game_id=1, user_id=1)

        assert task.game_id == 1
        assert task.user_id == 1
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0
        assert task.total_rounds == 0
        assert task.processed_rounds == 0
        assert task.result is None
        assert task.error is None
        assert task.task_id is not None  # UUID 自动生成
        assert isinstance(task.created_at, datetime)
        assert task.completed_at is None

    def test_mark_running(self):
        """测试标记为运行中状态"""
        task = EntityRecognitionTask(game_id=1, user_id=1)

        task.mark_running()

        assert task.status == TaskStatus.RUNNING

    def test_mark_completed(self):
        """测试标记为完成状态"""
        task = EntityRecognitionTask(game_id=1, user_id=1)
        result = {"items": [{"name": "测试物品"}], "characters": [], "landmarks": []}

        task.mark_completed(result)

        assert task.status == TaskStatus.COMPLETED
        assert task.progress == 100
        assert task.result == result
        assert task.completed_at is not None
        assert isinstance(task.completed_at, datetime)

    def test_mark_failed(self):
        """测试标记为失败状态"""
        task = EntityRecognitionTask(game_id=1, user_id=1)
        error_msg = "测试错误信息"

        task.mark_failed(error_msg)

        assert task.status == TaskStatus.FAILED
        assert task.error == error_msg
        assert task.completed_at is not None

    def test_update_progress(self):
        """测试进度更新"""
        task = EntityRecognitionTask(game_id=1, user_id=1)

        # 50% 进度
        task.update_progress(5, 10)
        assert task.progress == 50
        assert task.processed_rounds == 5
        assert task.total_rounds == 10

        # 75% 进度
        task.update_progress(3, 4)
        assert task.progress == 75
        assert task.processed_rounds == 3
        assert task.total_rounds == 4

        # 0% 进度（边界情况）
        task.update_progress(0, 10)
        assert task.progress == 0

        # 100% 进度（边界情况）
        task.update_progress(10, 10)
        assert task.progress == 100

    def test_to_dict(self):
        """测试转换为字典格式"""
        task = EntityRecognitionTask(game_id=1, user_id=1)
        task.mark_running()
        task.update_progress(5, 10)

        data = task.to_dict()

        assert data["task_id"] == task.task_id
        assert data["game_id"] == 1
        assert data["status"] == "running"
        assert data["progress"] == 50
        assert data["total_rounds"] == 10
        assert data["processed_rounds"] == 5
        assert "created_at" in data


class TestTaskManager:
    """测试 TaskManager 类"""

    def setup_method(self):
        """每个测试方法前重置任务管理器"""
        reset_task_manager()

    def test_create_task(self):
        """测试创建任务"""
        manager = get_task_manager()

        task = manager.create_task(game_id=1, user_id=1)

        assert task is not None
        assert task.game_id == 1
        assert task.user_id == 1
        assert task.task_id in manager._tasks
        assert manager._game_tasks[1] == task.task_id

    def test_get_task(self):
        """测试获取任务"""
        manager = get_task_manager()
        task = manager.create_task(game_id=1, user_id=1)

        # 获取存在的任务
        retrieved = manager.get_task(task.task_id)
        assert retrieved == task

        # 获取不存在的任务
        not_found = manager.get_task("non-existent-id")
        assert not_found is None

    def test_get_active_task_for_game(self):
        """测试获取游戏的活动任务"""
        manager = get_task_manager()

        # 创建任务
        task = manager.create_task(game_id=1, user_id=1)

        # 获取活动任务（pending 状态）
        active = manager.get_active_task_for_game(1)
        assert active == task

        # 标记为 running，仍然是活动任务
        task.mark_running()
        active = manager.get_active_task_for_game(1)
        assert active == task

        # 标记为 completed，不再是活动任务
        task.mark_completed({})
        active = manager.get_active_task_for_game(1)
        assert active is None

        # 标记为 failed，不再是活动任务
        task2 = manager.create_task(game_id=2, user_id=1)
        task2.mark_failed("error")
        active = manager.get_active_task_for_game(2)
        assert active is None

    def test_has_active_task(self):
        """测试检查是否有活动任务"""
        manager = get_task_manager()

        # 没有任务
        assert manager.has_active_task(1) is False

        # 创建任务
        manager.create_task(game_id=1, user_id=1)
        assert manager.has_active_task(1) is True

        # 其他游戏没有任务
        assert manager.has_active_task(2) is False

    def test_prevent_duplicate_task(self):
        """测试防重复启动逻辑"""
        manager = get_task_manager()

        # 创建第一个任务
        task1 = manager.create_task(game_id=1, user_id=1)

        # 检查活动任务
        active = manager.get_active_task_for_game(1)
        assert active.task_id == task1.task_id

        # 尝试创建第二个任务（应该通过检查防止）
        # 实际业务逻辑中应该在创建前检查 has_active_task
        assert manager.has_active_task(1) is True

    def test_cleanup_task(self):
        """测试清理任务"""
        manager = get_task_manager()
        task = manager.create_task(game_id=1, user_id=1)

        # 清理任务
        manager.cleanup_task(task.task_id)

        # 验证清理
        assert manager.get_task(task.task_id) is None
        assert 1 not in manager._game_tasks

    def test_cleanup_expired_tasks(self):
        """测试清理过期任务"""
        manager = get_task_manager()

        # 创建完成的任务（模拟1小时前完成）
        task1 = manager.create_task(game_id=1, user_id=1)
        task1.mark_completed({})
        task1.completed_at = datetime.now() - timedelta(hours=2)

        # 创建失败的任务（模拟1小时前完成）
        task2 = manager.create_task(game_id=2, user_id=1)
        task2.mark_failed("error")
        task2.completed_at = datetime.now() - timedelta(hours=2)

        # 创建进行中的任务
        task3 = manager.create_task(game_id=3, user_id=1)
        task3.mark_running()

        # 清理过期任务（保留1小时）
        manager.cleanup_expired_tasks(max_age_hours=1)

        # 验证：完成的任务和失败的任务被清理
        assert manager.get_task(task1.task_id) is None
        assert manager.get_task(task2.task_id) is None

        # 验证：进行中的任务保留
        assert manager.get_task(task3.task_id) == task3

    def test_get_stats(self):
        """测试获取统计信息"""
        manager = get_task_manager()

        # 创建各种状态的任务
        task1 = manager.create_task(game_id=1, user_id=1)
        task1.mark_running()

        task2 = manager.create_task(game_id=2, user_id=1)
        task2.mark_completed({})

        task3 = manager.create_task(game_id=3, user_id=1)
        task3.mark_failed("error")

        manager.create_task(game_id=4, user_id=1)
        # 保持 pending 状态

        stats = manager.get_stats()

        assert stats["total"] == 4
        assert stats["running"] == 1
        assert stats["completed"] == 1
        assert stats["failed"] == 1
        assert stats["pending"] == 1


class TestTaskStatusTransitions:
    """测试任务状态转换"""

    def test_pending_to_running(self):
        """测试 pending -> running 转换"""
        task = EntityRecognitionTask(game_id=1, user_id=1)
        assert task.status == TaskStatus.PENDING

        task.mark_running()
        assert task.status == TaskStatus.RUNNING

    def test_running_to_completed(self):
        """测试 running -> completed 转换"""
        task = EntityRecognitionTask(game_id=1, user_id=1)
        task.mark_running()

        result = {"items": []}
        task.mark_completed(result)

        assert task.status == TaskStatus.COMPLETED
        assert task.result == result

    def test_running_to_failed(self):
        """测试 running -> failed 转换"""
        task = EntityRecognitionTask(game_id=1, user_id=1)
        task.mark_running()

        task.mark_failed("error")

        assert task.status == TaskStatus.FAILED
        assert task.error == "error"

    def test_progress_updates_during_running(self):
        """测试运行期间进度更新"""
        task = EntityRecognitionTask(game_id=1, user_id=1)
        task.mark_running()

        # 模拟进度更新
        for i in range(1, 11):
            task.update_progress(i, 10)
            assert task.progress == i * 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
