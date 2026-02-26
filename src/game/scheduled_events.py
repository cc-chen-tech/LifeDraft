"""Scheduled Events System.

预定事件系统：确保角色做出的带有具体时间点的承诺在对应轮次强制触发。

核心功能：
1. 存储带有具体时间点的承诺
2. 在对应轮次检查并触发预定事件
3. 支持事件优先级和合并处理
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScheduledEvent:
    """预定事件：承诺在特定轮次强制触发的事件。
    
    当角色在故事中做出带有具体时间点的承诺时（如"下周三我一定去你家"），
    系统会创建一个 ScheduledEvent，确保在那个轮次该事件一定会发生。
    
    Attributes:
        event_id: 唯一标识符
        description: 承诺描述
        parties: 涉及的人物列表
        scheduled_week: 预定周数
        scheduled_round: 预定轮次（0=周一, 1=周中, 2=周末）
        event_hint: 事件提示（描述事件应该包含的内容）
        created_week: 创建时的周数
        created_round: 创建时的轮次
        source_commitment_id: 来源承诺ID（如果有）
        importance: 重要程度 critical/normal/minor
        status: 状态 pending/triggered/skipped/merged
        merged_into: 如果被合并，记录合并到的事件ID
    """
    event_id: str = ""
    description: str = ""
    parties: List[str] = field(default_factory=list)
    scheduled_week: int = -1
    scheduled_round: int = -1
    event_hint: str = ""
    
    created_week: int = 0
    created_round: int = 0
    source_commitment_id: str = ""
    importance: str = "normal"  # critical/normal/minor
    status: str = "pending"     # pending/triggered/skipped/merged
    merged_into: str = ""       # 如果被合并，记录合并到的事件ID
    
    def __post_init__(self):
        """自动生成事件ID（如果未提供）"""
        if not self.event_id:
            self.event_id = f"se_{uuid.uuid4().hex[:12]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "event_id": self.event_id,
            "description": self.description,
            "parties": self.parties,
            "scheduled_week": self.scheduled_week,
            "scheduled_round": self.scheduled_round,
            "event_hint": self.event_hint,
            "created_week": self.created_week,
            "created_round": self.created_round,
            "source_commitment_id": self.source_commitment_id,
            "importance": self.importance,
            "status": self.status,
            "merged_into": self.merged_into,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScheduledEvent":
        """从字典反序列化"""
        return cls(
            event_id=d.get("event_id", ""),
            description=d.get("description", ""),
            parties=d.get("parties", []),
            scheduled_week=d.get("scheduled_week", -1),
            scheduled_round=d.get("scheduled_round", -1),
            event_hint=d.get("event_hint", ""),
            created_week=d.get("created_week", 0),
            created_round=d.get("created_round", 0),
            source_commitment_id=d.get("source_commitment_id", ""),
            importance=d.get("importance", "normal"),
            status=d.get("status", "pending"),
            merged_into=d.get("merged_into", ""),
        )
    
    def matches_time(self, week: int, round_num: int) -> bool:
        """检查是否匹配指定的时间和轮次"""
        return self.scheduled_week == week and self.scheduled_round == round_num
    
    def is_overdue(self, current_week: int, current_round: int) -> bool:
        """检查是否已过期（错过了预定时间）"""
        if self.status != "pending":
            return False
        if self.scheduled_week < current_week:
            return True
        if self.scheduled_week == current_week and self.scheduled_round < current_round:
            return True
        return False
    
    def can_merge_with(self, other: "ScheduledEvent") -> bool:
        """检查是否可以与另一个预定事件合并
        
        合并条件：
        1. 同一时间点
        2. 有共同涉及人物
        3. 都处于pending状态
        """
        if self.status != "pending" or other.status != "pending":
            return False
        if self.scheduled_week != other.scheduled_week:
            return False
        if self.scheduled_round != other.scheduled_round:
            return False
        # 检查是否有共同人物
        common_parties = set(self.parties) & set(other.parties)
        return len(common_parties) > 0


def create_scheduled_event_from_commitment(
    description: str,
    parties: List[str],
    scheduled_week: int,
    scheduled_round: int,
    current_week: int,
    current_round: int,
    importance: str = "normal",
    event_hint: str = "",
    commitment_id: str = "",
) -> ScheduledEvent:
    """从承诺创建预定事件的便捷函数
    
    Args:
        description: 承诺描述
        parties: 涉及人物
        scheduled_week: 预定周数
        scheduled_round: 预定轮次
        current_week: 当前周数
        current_round: 当前轮次
        importance: 重要程度
        event_hint: 事件提示
        commitment_id: 来源承诺ID
    
    Returns:
        ScheduledEvent 实例
    """
    event = ScheduledEvent(
        description=description,
        parties=parties,
        scheduled_week=scheduled_week,
        scheduled_round=scheduled_round,
        event_hint=event_hint,
        created_week=current_week,
        created_round=current_round,
        source_commitment_id=commitment_id,
        importance=importance,
    )
    
    logger.info(
        f"📅 创建预定事件: {description[:40]}... "
        f"(第{scheduled_week}周, 轮次{scheduled_round}, 重要度:{importance})"
    )
    
    return event


def parse_time_reference(
    time_ref: str,
    current_week: int,
    current_round: int,
    language: str = "zh"
) -> Optional[Dict[str, int]]:
    """解析时间表述，计算具体的周数和轮次
    
    Args:
        time_ref: 时间表述（如"下周三"、"这周末"、"三天后"）
        current_week: 当前周数
        current_round: 当前轮次
        language: 语言
    
    Returns:
        包含 scheduled_week 和 scheduled_round 的字典，解析失败返回 None
    """
    time_ref_lower = time_ref.lower() if time_ref else ""
    
    if language == "zh":
        # 中文时间表述解析
        # 这周
        if "这周一" in time_ref or "今天" in time_ref:
            return {"scheduled_week": current_week, "scheduled_round": 0}
        if "这周中" in time_ref or "这周" in time_ref and "末" not in time_ref:
            return {"scheduled_week": current_week, "scheduled_round": 1}
        if "这周末" in time_ref:
            return {"scheduled_week": current_week, "scheduled_round": 2}
        
        # 下周
        if "下周一" in time_ref:
            return {"scheduled_week": current_week + 1, "scheduled_round": 0}
        if "下周中" in time_ref or "下周" in time_ref and "末" not in time_ref:
            return {"scheduled_week": current_week + 1, "scheduled_round": 1}
        if "下周末" in time_ref:
            return {"scheduled_week": current_week + 1, "scheduled_round": 2}
        
        # 下下周
        if "下下周一" in time_ref:
            return {"scheduled_week": current_week + 2, "scheduled_round": 0}
        if "下下周" in time_ref:
            return {"scheduled_week": current_week + 2, "scheduled_round": 1}
        
        # X天后
        import re
        days_match = re.search(r"(\d+)天[后以]", time_ref)
        if days_match:
            days = int(days_match.group(1))
            # 每3轮=1周，计算目标周和轮次
            total_rounds = current_round + days
            target_week = current_week + (total_rounds // 3)
            target_round = total_rounds % 3
            return {"scheduled_week": target_week, "scheduled_round": target_round}
        
        # 明天/后天
        if "明天" in time_ref:
            next_round = current_round + 1
            target_week = current_week + (next_round // 3)
            target_round = next_round % 3
            return {"scheduled_week": target_week, "scheduled_round": target_round}
        if "后天" in time_ref:
            next_round = current_round + 2
            target_week = current_week + (next_round // 3)
            target_round = next_round % 3
            return {"scheduled_week": target_week, "scheduled_round": target_round}
    
    else:
        # 英文时间表述解析
        # ★ 注意：必须先检查更具体的模式（如 this weekend），再检查更通用的模式（如 this week）
        if "this monday" in time_ref_lower or "today" in time_ref_lower:
            return {"scheduled_week": current_week, "scheduled_round": 0}
        if "this weekend" in time_ref_lower:
            return {"scheduled_week": current_week, "scheduled_round": 2}
        if "this midweek" in time_ref_lower or "this week" in time_ref_lower:
            return {"scheduled_week": current_week, "scheduled_round": 1}
        
        if "next monday" in time_ref_lower:
            return {"scheduled_week": current_week + 1, "scheduled_round": 0}
        if "next midweek" in time_ref_lower or "next week" in time_ref_lower:
            return {"scheduled_week": current_week + 1, "scheduled_round": 1}
        if "next weekend" in time_ref_lower:
            return {"scheduled_week": current_week + 1, "scheduled_round": 2}
        
        import re
        days_match = re.search(r"(\d+)\s*days?\s*(later|after|from now)", time_ref_lower)
        if days_match:
            days = int(days_match.group(1))
            total_rounds = current_round + days
            target_week = current_week + (total_rounds // 3)
            target_round = total_rounds % 3
            return {"scheduled_week": target_week, "scheduled_round": target_round}
        
        if "tomorrow" in time_ref_lower:
            next_round = current_round + 1
            target_week = current_week + (next_round // 3)
            target_round = next_round % 3
            return {"scheduled_week": target_week, "scheduled_round": target_round}
        if "day after tomorrow" in time_ref_lower or "in two days" in time_ref_lower:
            next_round = current_round + 2
            target_week = current_week + (next_round // 3)
            target_round = next_round % 3
            return {"scheduled_week": target_week, "scheduled_round": target_round}
    
    return None


class ScheduledEventManager:
    """预定事件管理器
    
    负责：
    1. 管理预定事件的存储和检索
    2. 检查当前轮次是否有预定事件需要触发
    3. 处理事件合并和优先级排序
    4. 处理错过的事件
    """
    
    def __init__(self):
        self.events: List[ScheduledEvent] = []
    
    def add_event(self, event: ScheduledEvent) -> None:
        """添加预定事件"""
        # 检查是否已存在相同ID的事件
        existing = next((e for e in self.events if e.event_id == event.event_id), None)
        if existing:
            logger.warning(f"预定事件已存在: {event.event_id}")
            return
        
        self.events.append(event)
        logger.info(f"添加预定事件: {event.description[:40]}... (ID: {event.event_id})")
    
    def remove_event(self, event_id: str) -> bool:
        """移除预定事件"""
        for i, event in enumerate(self.events):
            if event.event_id == event_id:
                self.events.pop(i)
                logger.info(f"移除预定事件: {event_id}")
                return True
        return False
    
    def get_pending_events_for_round(self, week: int, round_num: int) -> List[ScheduledEvent]:
        """获取指定轮次需要触发的预定事件
        
        Returns:
            按优先级排序的预定事件列表
        """
        pending = [
            e for e in self.events
            if e.status == "pending" and e.matches_time(week, round_num)
        ]
        
        # 按重要程度排序：critical > normal > minor
        importance_order = {"critical": 0, "normal": 1, "minor": 2}
        pending.sort(key=lambda e: (importance_order.get(e.importance, 1), e.created_week))
        
        return pending
    
    def get_overdue_events(self, current_week: int, current_round: int) -> List[ScheduledEvent]:
        """获取已过期的预定事件"""
        return [e for e in self.events if e.is_overdue(current_week, current_round)]
    
    def mark_triggered(self, event_id: str) -> None:
        """标记事件已触发"""
        for event in self.events:
            if event.event_id == event_id:
                event.status = "triggered"
                logger.info(f"预定事件已触发: {event.description[:40]}...")
                break
    
    def mark_skipped(self, event_id: str) -> None:
        """标记事件已跳过"""
        for event in self.events:
            if event.event_id == event_id:
                event.status = "skipped"
                logger.warning(f"预定事件被跳过: {event.description[:40]}...")
                break
    
    def merge_events(self, event1: ScheduledEvent, event2: ScheduledEvent) -> ScheduledEvent:
        """合并两个预定事件
        
        返回合并后的新事件，原事件标记为 merged
        """
        # 合并描述
        merged_desc = f"{event1.description}；同时{event2.description}"
        
        # 合并人物（去重）
        merged_parties = list(set(event1.parties + event2.parties))
        
        # 取较高的重要程度
        importance_order = {"critical": 0, "normal": 1, "minor": 2}
        merged_importance = event1.importance
        if importance_order.get(event2.importance, 1) < importance_order.get(merged_importance, 1):
            merged_importance = event2.importance
        
        # 合并事件提示
        merged_hint = f"{event1.event_hint}；{event2.event_hint}".strip("；")
        
        merged = ScheduledEvent(
            description=merged_desc,
            parties=merged_parties,
            scheduled_week=event1.scheduled_week,
            scheduled_round=event1.scheduled_round,
            event_hint=merged_hint,
            created_week=min(event1.created_week, event2.created_week),
            created_round=min(event1.created_round, event2.created_round),
            importance=merged_importance,
        )
        
        # 标记原事件为已合并
        event1.status = "merged"
        event1.merged_into = merged.event_id
        event2.status = "merged"
        event2.merged_into = merged.event_id
        
        logger.info(f"合并预定事件: {event1.event_id} + {event2.event_id} -> {merged.event_id}")
        
        return merged
    
    def cleanup_old_events(self, current_week: int, keep_weeks: int = 10) -> int:
        """清理旧的已处理事件
        
        Args:
            current_week: 当前周数
            keep_weeks: 保留最近多少周的事件
        
        Returns:
            清理的事件数量
        """
        to_remove = []
        for event in self.events:
            if event.status in ("triggered", "skipped", "merged"):
                if current_week - event.scheduled_week > keep_weeks:
                    to_remove.append(event.event_id)
        
        for event_id in to_remove:
            self.remove_event(event_id)
        
        if to_remove:
            logger.info(f"清理了 {len(to_remove)} 个旧的预定事件")
        
        return len(to_remove)
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """序列化为字典列表"""
        return [e.to_dict() for e in self.events]
    
    @classmethod
    def from_dict_list(cls, data: List[Dict[str, Any]]) -> "ScheduledEventManager":
        """从字典列表反序列化"""
        manager = cls()
        for item in data:
            manager.events.append(ScheduledEvent.from_dict(item))
        return manager
