"""实体识别任务管理模块

提供异步实体识别任务的状态管理、进度跟踪和结果存储。
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"  # 等待中
    RUNNING = "running"  # 进行中
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失败


@dataclass
class EntityRecognitionTask:
    """实体识别任务

    用于跟踪异步实体识别的状态、进度和结果。

    Attributes:
        task_id: 任务唯一标识符
        game_id: 关联的游戏ID
        user_id: 关联的用户ID
        status: 当前任务状态
        progress: 进度百分比 (0-100)
        total_rounds: 总轮次数
        processed_rounds: 已处理轮次数
        result: 识别结果
        error: 错误信息
        created_at: 创建时间
        completed_at: 完成时间
    """

    game_id: int
    user_id: int
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    total_rounds: int = 0
    processed_rounds: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于API返回）"""
        return {
            "task_id": self.task_id,
            "game_id": self.game_id,
            "status": self.status.value,
            "progress": self.progress,
            "total_rounds": self.total_rounds,
            "processed_rounds": self.processed_rounds,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    def mark_running(self):
        """标记为运行中"""
        self.status = TaskStatus.RUNNING

    def mark_completed(self, result: Dict[str, Any]):
        """标记为完成"""
        self.status = TaskStatus.COMPLETED
        self.progress = 100
        self.result = result
        self.completed_at = datetime.now()

    def mark_failed(self, error: str):
        """标记为失败"""
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()

    def update_progress(self, processed: int, total: int):
        """更新进度"""
        self.processed_rounds = processed
        self.total_rounds = total
        if total > 0:
            self.progress = int(processed / total * 100)


class TaskManager:
    """任务管理器

    管理所有实体识别任务的生命周期，提供任务创建、查询、清理等功能。
    """

    def __init__(self):
        # 任务存储：task_id -> EntityRecognitionTask
        self._tasks: Dict[str, EntityRecognitionTask] = {}
        # 游戏任务映射：game_id -> task_id（用于防重复）
        self._game_tasks: Dict[int, str] = {}

    def create_task(self, game_id: int, user_id: int) -> EntityRecognitionTask:
        """创建新任务

        Args:
            game_id: 游戏ID
            user_id: 用户ID

        Returns:
            新创建的任务对象
        """
        task = EntityRecognitionTask(game_id=game_id, user_id=user_id)
        self._tasks[task.task_id] = task
        self._game_tasks[game_id] = task.task_id
        return task

    def get_task(self, task_id: str) -> Optional[EntityRecognitionTask]:
        """获取任务

        Args:
            task_id: 任务ID

        Returns:
            任务对象，不存在则返回 None
        """
        return self._tasks.get(task_id)

    def get_active_task_for_game(self, game_id: int) -> Optional[EntityRecognitionTask]:
        """获取游戏当前进行中的任务

        Args:
            game_id: 游戏ID

        Returns:
            进行中的任务对象，不存在则返回 None
        """
        task_id = self._game_tasks.get(game_id)
        if task_id:
            task = self._tasks.get(task_id)
            if task and task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                return task
        return None

    def has_active_task(self, game_id: int) -> bool:
        """检查是否有进行中的任务

        Args:
            game_id: 游戏ID

        Returns:
            是否有进行中的任务
        """
        return self.get_active_task_for_game(game_id) is not None

    def cleanup_task(self, task_id: str):
        """清理任务

        Args:
            task_id: 任务ID
        """
        task = self._tasks.get(task_id)
        if task:
            # 从游戏任务映射中移除
            if self._game_tasks.get(task.game_id) == task_id:
                del self._game_tasks[task.game_id]
            # 从任务存储中移除
            del self._tasks[task_id]

    def cleanup_expired_tasks(self, max_age_hours: int = 1):
        """清理过期任务

        清理已完成或失败超过指定时间的任务，防止内存泄漏。

        Args:
            max_age_hours: 最大保留时间（小时）
        """
        from datetime import timedelta

        expired_time = datetime.now() - timedelta(hours=max_age_hours)
        tasks_to_remove = []

        for task_id, task in self._tasks.items():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                if task.completed_at and task.completed_at < expired_time:
                    tasks_to_remove.append(task_id)

        # 清理并记录日志
        for task_id in tasks_to_remove:
            task = self._tasks.get(task_id)  # type: ignore
            if task:
                logger.info(
                    f"[TaskCleanup] Removing expired task {task_id} "
                    f"(game={task.game_id}, status={task.status.value}, "
                    f"completed_at={task.completed_at.isoformat()})"  # type: ignore
                )
            self.cleanup_task(task_id)

        if tasks_to_remove:
            logger.info(
                f"[TaskCleanup] Cleaned up {len(tasks_to_remove)} expired tasks"
            )
        else:
            logger.info("[TaskCleanup] No expired tasks to clean up")

    def get_stats(self) -> Dict[str, int]:
        """获取任务统计

        Returns:
            任务统计信息
        """
        stats = {
            "total": len(self._tasks),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
        }

        for task in self._tasks.values():
            stats[task.status.value] += 1

        return stats


# 全局任务管理器实例
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取全局任务管理器实例

    Returns:
        TaskManager 实例
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


def reset_task_manager():
    """重置任务管理器（主要用于测试）"""
    global _task_manager
    _task_manager = None
