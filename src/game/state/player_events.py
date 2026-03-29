"""玩家预定事件管理逻辑。

此模块定义了 PlayerState 的预定事件管理部分，作为 Mixin 类供 PlayerState 继承。
包含预定事件的添加、获取、触发标记和过期检测等方法。
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.game.scheduled_events import ScheduledEvent, ScheduledEventManager

logger = logging.getLogger(__name__)


class PlayerEventsMixin:
    """玩家预定事件管理 Mixin。

    包含预定事件的增删改查和状态同步方法。
    """

    # 类型声明：这些属性由 PlayerDataMixin 定义，在组合类中可用
    scheduled_events: List[Dict[str, Any]]
    week: int
    current_round: int

    def add_scheduled_event(self, event: "ScheduledEvent") -> None:
        """添加一个预定事件

        Args:
            event: ScheduledEvent 实例
        """
        from src.game.scheduled_events import ScheduledEvent

        # 检查是否已存在
        existing_ids = [e.get("event_id") for e in self.scheduled_events]
        if event.event_id not in existing_ids:
            self.scheduled_events.append(event.to_dict())
            logger.debug(f"添加预定事件: {event.description[:40]}... (ID: {event.event_id})")

    def get_scheduled_event_manager(self) -> "ScheduledEventManager":
        """获取预定事件管理器实例

        Returns:
            ScheduledEventManager 实例
        """
        from src.game.scheduled_events import ScheduledEventManager

        return ScheduledEventManager.from_dict_list(self.scheduled_events)

    def sync_scheduled_events_from_manager(self, manager: "ScheduledEventManager") -> None:
        """从管理器同步预定事件状态

        Args:
            manager: ScheduledEventManager 实例
        """
        self.scheduled_events = manager.to_dict_list()

    def get_pending_scheduled_events(
        self, week: Optional[int] = None, round_num: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取待触发的预定事件

        Args:
            week: 指定周数，默认当前周
            round_num: 指定轮次，默认当前轮次

        Returns:
            预定事件字典列表
        """
        target_week = week if week is not None else self.week
        target_round = round_num if round_num is not None else self.current_round

        pending = []
        for e in self.scheduled_events:
            if e.get("status") != "pending":
                continue
            if e.get("scheduled_week") == target_week and e.get("scheduled_round") == target_round:
                pending.append(e)

        # 按重要程度排序
        from src.game.constants import IMPORTANCE_ORDER

        pending.sort(key=lambda e: IMPORTANCE_ORDER.get(e.get("importance", "normal"), 2))

        return pending

    def mark_scheduled_event_triggered(self, event_id: str) -> bool:
        """标记预定事件已触发

        Args:
            event_id: 事件ID

        Returns:
            是否成功标记
        """
        for e in self.scheduled_events:
            if e.get("event_id") == event_id:
                e["status"] = "triggered"
                logger.info(f"预定事件已触发: {event_id}")
                return True
        return False

    def get_overdue_scheduled_events(self) -> List[Dict[str, Any]]:
        """获取已过期的预定事件

        Returns:
            过期的预定事件列表
        """
        overdue = []
        for e in self.scheduled_events:
            if e.get("status") != "pending":
                continue
            scheduled_week = e.get("scheduled_week", -1)
            scheduled_round = e.get("scheduled_round", -1)

            if scheduled_week < self.week:
                overdue.append(e)
            elif scheduled_week == self.week and scheduled_round < self.current_round:
                overdue.append(e)

        return overdue
