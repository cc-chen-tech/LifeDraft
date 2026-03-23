"""Tests for the Scheduled Events System.

预定事件系统测试：确保角色承诺在指定轮次强制触发。
"""

import pytest

from src.game.scheduled_events import (
    ScheduledEvent,
    ScheduledEventManager,
    create_scheduled_event_from_commitment,
    parse_time_reference,
)
from src.game.state.player_state import PlayerState
from src.game.world_model import Commitment


class TestScheduledEvent:
    """测试 ScheduledEvent 数据类"""

    def test_create_scheduled_event(self):
        """测试创建预定事件"""
        event = ScheduledEvent(
            description="去李明家帮他搬家",
            parties=["李明"],
            scheduled_week=5,
            scheduled_round=0,
            created_week=4,
            created_round=1,
            importance="normal",
        )

        assert event.description == "去李明家帮他搬家"
        assert event.parties == ["李明"]
        assert event.scheduled_week == 5
        assert event.scheduled_round == 0
        assert event.status == "pending"
        assert event.importance == "normal"
        assert event.event_id.startswith("se_")

    def test_auto_generate_event_id(self):
        """测试自动生成事件ID"""
        event = ScheduledEvent(description="test")
        assert event.event_id.startswith("se_")
        assert len(event.event_id) == 15  # "se_" + 12 hex chars

    def test_to_dict_and_from_dict(self):
        """测试序列化和反序列化"""
        event = ScheduledEvent(
            event_id="se_test123",
            description="测试事件",
            parties=["张三", "李四"],
            scheduled_week=10,
            scheduled_round=2,
            event_hint="这是一个测试",
            created_week=8,
            created_round=1,
            importance="critical",
        )

        # 序列化
        d = event.to_dict()
        assert d["event_id"] == "se_test123"
        assert d["description"] == "测试事件"
        assert d["parties"] == ["张三", "李四"]
        assert d["scheduled_week"] == 10
        assert d["scheduled_round"] == 2

        # 反序列化
        event2 = ScheduledEvent.from_dict(d)
        assert event2.event_id == event.event_id
        assert event2.description == event.description
        assert event2.parties == event.parties
        assert event2.scheduled_week == event.scheduled_week

    def test_matches_time(self):
        """测试时间匹配"""
        event = ScheduledEvent(
            scheduled_week=5,
            scheduled_round=1,
        )

        assert event.matches_time(5, 1) is True
        assert event.matches_time(5, 0) is False
        assert event.matches_time(4, 1) is False

    def test_is_overdue(self):
        """测试过期检测"""
        event = ScheduledEvent(
            scheduled_week=5,
            scheduled_round=1,
            status="pending",
        )

        # 未过期
        assert event.is_overdue(4, 0) is False
        assert event.is_overdue(5, 0) is False
        assert event.is_overdue(5, 1) is False

        # 已过期
        assert event.is_overdue(6, 0) is True
        assert event.is_overdue(5, 2) is True

        # 非pending状态不算过期
        event.status = "triggered"
        assert event.is_overdue(6, 0) is False

    def test_can_merge_with(self):
        """测试合并检测"""
        event1 = ScheduledEvent(
            description="帮李明搬家",
            parties=["李明"],
            scheduled_week=5,
            scheduled_round=0,
        )

        # 可以合并：同一时间，有共同人物
        event2 = ScheduledEvent(
            description="和李明吃饭",
            parties=["李明", "王五"],
            scheduled_week=5,
            scheduled_round=0,
        )
        assert event1.can_merge_with(event2) is True

        # 不能合并：不同时间
        event3 = ScheduledEvent(
            description="和李明吃饭",
            parties=["李明"],
            scheduled_week=6,
            scheduled_round=0,
        )
        assert event1.can_merge_with(event3) is False

        # 不能合并：无共同人物
        event4 = ScheduledEvent(
            description="和张三吃饭",
            parties=["张三"],
            scheduled_week=5,
            scheduled_round=0,
        )
        assert event1.can_merge_with(event4) is False


class TestScheduledEventManager:
    """测试预定事件管理器"""

    def test_add_and_get_events(self):
        """测试添加和获取事件"""
        manager = ScheduledEventManager()

        event = ScheduledEvent(
            description="测试事件",
            scheduled_week=5,
            scheduled_round=0,
        )

        manager.add_event(event)
        assert len(manager.events) == 1

        # 重复添加会被跳过
        manager.add_event(event)
        assert len(manager.events) == 1

    def test_get_pending_events_for_round(self):
        """测试获取指定轮次的待触发事件"""
        manager = ScheduledEventManager()

        # 添加多个事件
        event1 = ScheduledEvent(
            description="事件1",
            scheduled_week=5,
            scheduled_round=0,
            importance="normal",
        )
        event2 = ScheduledEvent(
            description="事件2",
            scheduled_week=5,
            scheduled_round=0,
            importance="critical",  # 更高优先级
        )
        event3 = ScheduledEvent(
            description="事件3",
            scheduled_week=5,
            scheduled_round=1,  # 不同轮次
        )
        event4 = ScheduledEvent(
            description="事件4",
            scheduled_week=5,
            scheduled_round=0,
            status="triggered",  # 已触发
        )

        manager.add_event(event1)
        manager.add_event(event2)
        manager.add_event(event3)
        manager.add_event(event4)

        # 获取第5周轮次0的待触发事件
        pending = manager.get_pending_events_for_round(5, 0)
        assert len(pending) == 2

        # critical 优先级的事件应该排在前面
        assert pending[0].importance == "critical"
        assert pending[1].importance == "normal"

    def test_get_overdue_events(self):
        """测试获取过期事件"""
        manager = ScheduledEventManager()

        event1 = ScheduledEvent(
            description="过期事件",
            scheduled_week=4,
            scheduled_round=0,
        )
        event2 = ScheduledEvent(
            description="未过期事件",
            scheduled_week=6,
            scheduled_round=0,
        )

        manager.add_event(event1)
        manager.add_event(event2)

        overdue = manager.get_overdue_events(5, 0)
        assert len(overdue) == 1
        assert overdue[0].description == "过期事件"

    def test_mark_triggered(self):
        """测试标记事件已触发"""
        manager = ScheduledEventManager()

        event = ScheduledEvent(
            event_id="se_test001",
            description="测试事件",
            scheduled_week=5,
            scheduled_round=0,
        )

        manager.add_event(event)
        manager.mark_triggered("se_test001")

        assert event.status == "triggered"

    def test_merge_events(self):
        """测试合并事件"""
        manager = ScheduledEventManager()

        event1 = ScheduledEvent(
            description="帮李明搬家",
            parties=["李明"],
            scheduled_week=5,
            scheduled_round=0,
            importance="normal",
        )
        event2 = ScheduledEvent(
            description="和李明吃饭",
            parties=["李明", "王五"],
            scheduled_week=5,
            scheduled_round=0,
            importance="critical",
        )

        manager.add_event(event1)
        manager.add_event(event2)

        merged = manager.merge_events(event1, event2)

        assert "帮李明搬家" in merged.description
        assert "和李明吃饭" in merged.description
        assert "李明" in merged.parties
        assert "王五" in merged.parties
        assert merged.importance == "critical"  # 取较高的重要程度
        assert event1.status == "merged"
        assert event2.status == "merged"

    def test_cleanup_old_events(self):
        """测试清理旧事件"""
        manager = ScheduledEventManager()

        # 已触发的旧事件
        old_event = ScheduledEvent(
            description="旧事件",
            scheduled_week=1,
            status="triggered",
        )
        # 新事件
        new_event = ScheduledEvent(
            description="新事件",
            scheduled_week=15,
            status="triggered",
        )

        manager.add_event(old_event)
        manager.add_event(new_event)

        # 清理超过10周的事件
        removed = manager.cleanup_old_events(15, keep_weeks=10)
        assert removed == 1
        assert len(manager.events) == 1
        assert manager.events[0].description == "新事件"


class TestParseTimeReference:
    """测试时间表述解析"""

    def test_parse_this_week_zh(self):
        """测试中文'这周'表述"""
        # 这周一
        result = parse_time_reference(
            "这周一", current_week=5, current_round=1, language="zh"
        )
        assert result == {"scheduled_week": 5, "scheduled_round": 0}

        # 这周末
        result = parse_time_reference(
            "这周末", current_week=5, current_round=1, language="zh"
        )
        assert result == {"scheduled_week": 5, "scheduled_round": 2}

    def test_parse_next_week_zh(self):
        """测试中文'下周'表述"""
        # 下周一
        result = parse_time_reference(
            "下周一", current_week=5, current_round=1, language="zh"
        )
        assert result == {"scheduled_week": 6, "scheduled_round": 0}

        # 下周末
        result = parse_time_reference(
            "下周末", current_week=5, current_round=1, language="zh"
        )
        assert result == {"scheduled_week": 6, "scheduled_round": 2}

    def test_parse_days_later_zh(self):
        """测试中文'X天后'表述"""
        # 明天
        result = parse_time_reference(
            "明天", current_week=5, current_round=0, language="zh"
        )
        assert result == {"scheduled_week": 5, "scheduled_round": 1}

        # 后天
        result = parse_time_reference(
            "后天", current_week=5, current_round=0, language="zh"
        )
        assert result == {"scheduled_week": 5, "scheduled_round": 2}

        # 明天（从轮次2开始，会跨周）
        result = parse_time_reference(
            "明天", current_week=5, current_round=2, language="zh"
        )
        assert result == {"scheduled_week": 6, "scheduled_round": 0}

    def test_parse_english(self):
        """测试英文时间表述"""
        # next Monday
        result = parse_time_reference(
            "next Monday", current_week=5, current_round=1, language="en"
        )
        assert result == {"scheduled_week": 6, "scheduled_round": 0}

        # this weekend
        result = parse_time_reference(
            "this weekend", current_week=5, current_round=1, language="en"
        )
        assert result == {"scheduled_week": 5, "scheduled_round": 2}

        # tomorrow
        result = parse_time_reference(
            "tomorrow", current_week=5, current_round=0, language="en"
        )
        assert result == {"scheduled_week": 5, "scheduled_round": 1}

        # this midweek
        result = parse_time_reference(
            "this midweek", current_week=5, current_round=0, language="en"
        )
        assert result == {"scheduled_week": 5, "scheduled_round": 1}

    def test_parse_invalid(self):
        """测试无效时间表述"""
        # 模糊表述返回None
        result = parse_time_reference(
            "有机会", current_week=5, current_round=1, language="zh"
        )
        assert result is None

        result = parse_time_reference(
            "sometime", current_week=5, current_round=1, language="en"
        )
        assert result is None


class TestCommitment:
    """测试扩展的 Commitment 类"""

    def test_commitment_with_schedule(self):
        """测试带预定信息的承诺"""
        commitment = Commitment(
            description="下周三去李明家",
            parties=["李明"],
            deadline_week=6,
            scheduled_week=6,
            scheduled_round=0,
            event_hint="帮忙搬家",
        )

        assert commitment.is_scheduled() is True
        assert commitment.scheduled_week == 6
        assert commitment.scheduled_round == 0

    def test_commitment_without_schedule(self):
        """测试无预定信息的承诺"""
        commitment = Commitment(
            description="有机会一起吃饭",
            parties=["李明"],
        )

        assert commitment.is_scheduled() is False


class TestPlayerStateScheduledEvents:
    """测试 PlayerState 的预定事件管理"""

    def test_add_scheduled_event(self):
        """测试添加预定事件"""
        state = PlayerState()

        event = ScheduledEvent(
            description="测试事件",
            scheduled_week=5,
            scheduled_round=0,
        )

        state.add_scheduled_event(event)
        assert len(state.scheduled_events) == 1

    def test_get_pending_scheduled_events(self):
        """测试获取待触发事件"""
        state = PlayerState(week=5, current_round=0)

        event1 = ScheduledEvent(
            description="当前轮次事件",
            scheduled_week=5,
            scheduled_round=0,
        ).to_dict()
        event2 = ScheduledEvent(
            description="其他轮次事件",
            scheduled_week=5,
            scheduled_round=1,
        ).to_dict()

        state.scheduled_events = [event1, event2]

        pending = state.get_pending_scheduled_events()
        assert len(pending) == 1
        assert pending[0]["description"] == "当前轮次事件"

    def test_mark_scheduled_event_triggered(self):
        """测试标记事件已触发"""
        state = PlayerState()

        event = ScheduledEvent(
            event_id="se_test001",
            description="测试事件",
            scheduled_week=5,
            scheduled_round=0,
        ).to_dict()

        state.scheduled_events = [event]

        result = state.mark_scheduled_event_triggered("se_test001")
        assert result is True
        assert state.scheduled_events[0]["status"] == "triggered"

    def test_get_overdue_scheduled_events(self):
        """测试获取过期事件"""
        state = PlayerState(week=6, current_round=0)

        event1 = ScheduledEvent(
            description="过期事件",
            scheduled_week=5,
            scheduled_round=0,
        ).to_dict()
        event2 = ScheduledEvent(
            description="当前事件",
            scheduled_week=6,
            scheduled_round=0,
        ).to_dict()

        state.scheduled_events = [event1, event2]

        overdue = state.get_overdue_scheduled_events()
        assert len(overdue) == 1
        assert overdue[0]["description"] == "过期事件"


class TestCreateScheduledEventFromCommitment:
    """测试从承诺创建预定事件"""

    def test_create_from_commitment(self):
        """测试创建过程"""
        event = create_scheduled_event_from_commitment(
            description="去李明家帮忙",
            parties=["李明"],
            scheduled_week=6,
            scheduled_round=0,
            current_week=5,
            current_round=1,
            importance="normal",
            event_hint="搬家",
        )

        assert event.description == "去李明家帮忙"
        assert event.parties == ["李明"]
        assert event.scheduled_week == 6
        assert event.scheduled_round == 0
        assert event.created_week == 5
        assert event.created_round == 1
        assert event.importance == "normal"
        assert event.event_hint == "搬家"
