"""Scheduled events contract tests.

No mocks. Pure logic tests for event scheduling system.
"""

from src.game.scheduled_events import (ScheduledEvent, ScheduledEventManager,
                                       parse_time_reference)


class TestScheduledEventContract:
    """Contract tests for ScheduledEvent."""

    def test_event_auto_id(self):
        """Event without ID should auto-generate one."""
        event = ScheduledEvent(description="Test")
        assert event.event_id.startswith("se_")
        assert len(event.event_id) == 15

    def test_event_preserves_id(self):
        """Event with provided ID should keep it."""
        event = ScheduledEvent(event_id="custom_id", description="Test")
        assert event.event_id == "custom_id"

    def test_matches_time_true(self):
        """matches_time should return True for matching week/round."""
        event = ScheduledEvent(scheduled_week=5, scheduled_round=1)
        assert event.matches_time(5, 1) is True

    def test_matches_time_false(self):
        """matches_time should return False for non-matching time."""
        event = ScheduledEvent(scheduled_week=5, scheduled_round=1)
        assert event.matches_time(5, 2) is False
        assert event.matches_time(6, 1) is False

    def test_is_overdue_past_week(self):
        """Event in past week should be overdue."""
        event = ScheduledEvent(scheduled_week=3, scheduled_round=0, status="pending")
        assert event.is_overdue(5, 0) is True

    def test_is_overdue_same_week_past_round(self):
        """Event in same week but past round should be overdue."""
        event = ScheduledEvent(scheduled_week=5, scheduled_round=0, status="pending")
        assert event.is_overdue(5, 2) is True

    def test_is_overdue_not_pending(self):
        """Non-pending event should not be overdue."""
        event = ScheduledEvent(scheduled_week=3, scheduled_round=0, status="triggered")
        assert event.is_overdue(5, 0) is False

    def test_is_overdue_future(self):
        """Future event should not be overdue."""
        event = ScheduledEvent(scheduled_week=10, scheduled_round=0, status="pending")
        assert event.is_overdue(5, 0) is False

    def test_can_merge_with_same_time_common_party(self):
        """Events at same time with common party should merge."""
        e1 = ScheduledEvent(
            scheduled_week=5, scheduled_round=1, parties=["Alice"], status="pending"
        )
        e2 = ScheduledEvent(
            scheduled_week=5,
            scheduled_round=1,
            parties=["Alice", "Bob"],
            status="pending",
        )
        assert e1.can_merge_with(e2) is True

    def test_can_merge_with_no_common_party(self):
        """Events with no common party should not merge."""
        e1 = ScheduledEvent(
            scheduled_week=5, scheduled_round=1, parties=["Alice"], status="pending"
        )
        e2 = ScheduledEvent(scheduled_week=5, scheduled_round=1, parties=["Bob"], status="pending")
        assert e1.can_merge_with(e2) is False

    def test_can_merge_with_different_time(self):
        """Events at different times should not merge."""
        e1 = ScheduledEvent(
            scheduled_week=5, scheduled_round=1, parties=["Alice"], status="pending"
        )
        e2 = ScheduledEvent(
            scheduled_week=6, scheduled_round=1, parties=["Alice"], status="pending"
        )
        assert e1.can_merge_with(e2) is False

    def test_can_merge_with_non_pending(self):
        """Non-pending events should not merge."""
        e1 = ScheduledEvent(
            scheduled_week=5, scheduled_round=1, parties=["Alice"], status="pending"
        )
        e2 = ScheduledEvent(
            scheduled_week=5, scheduled_round=1, parties=["Alice"], status="triggered"
        )
        assert e1.can_merge_with(e2) is False

    def test_to_dict_roundtrip(self):
        """to_dict and from_dict should be inverse."""
        event = ScheduledEvent(
            event_id="test_id",
            description="Test desc",
            parties=["Alice"],
            scheduled_week=5,
            scheduled_round=1,
            importance="critical",
            status="pending",
        )
        d = event.to_dict()
        restored = ScheduledEvent.from_dict(d)
        assert restored.event_id == event.event_id
        assert restored.description == event.description
        assert restored.parties == event.parties
        assert restored.importance == event.importance


class TestParseTimeReferenceContract:
    """Contract tests for time reference parsing."""

    def test_zh_this_monday(self):
        """这周一 should map to current week round 0."""
        result = parse_time_reference(
            "这周一我去找你", current_week=5, current_round=1, language="zh"
        )
        assert result == {"scheduled_week": 5, "scheduled_round": 0}

    def test_zh_today(self):
        """今天 should map to current week/current round."""
        result = parse_time_reference("今天见面", current_week=5, current_round=1, language="zh")
        assert result == {"scheduled_week": 5, "scheduled_round": 0}

    def test_zh_this_weekend(self):
        """这周末 should map to current week round 2."""
        result = parse_time_reference("这周末聚餐", current_week=5, current_round=0, language="zh")
        assert result == {"scheduled_week": 5, "scheduled_round": 2}

    def test_zh_next_monday(self):
        """下周一 should map to next week round 0."""
        result = parse_time_reference("下周一开会", current_week=5, current_round=0, language="zh")
        assert result == {"scheduled_week": 6, "scheduled_round": 0}

    def test_zh_next_weekend(self):
        """下周末 should map to next week round 2."""
        result = parse_time_reference("下周末旅行", current_week=5, current_round=0, language="zh")
        assert result == {"scheduled_week": 6, "scheduled_round": 2}

    def test_zh_tomorrow(self):
        """明天 should advance by one round."""
        result = parse_time_reference("明天见", current_week=5, current_round=0, language="zh")
        assert result == {"scheduled_week": 5, "scheduled_round": 1}

    def test_zh_tomorrow_cross_week(self):
        """明天 from round 2 should cross to next week."""
        result = parse_time_reference("明天见", current_week=5, current_round=2, language="zh")
        assert result == {"scheduled_week": 6, "scheduled_round": 0}

    def test_zh_day_after_tomorrow(self):
        """后天 should advance by two rounds."""
        result = parse_time_reference("后天见面", current_week=5, current_round=0, language="zh")
        assert result == {"scheduled_week": 5, "scheduled_round": 2}

    def test_zh_next_month(self):
        """下月 should map to about 4 weeks later."""
        result = parse_time_reference("下月见面", current_week=5, current_round=0, language="zh")
        assert result == {"scheduled_week": 9, "scheduled_round": 0}

    def test_zh_x_days_later(self):
        """X天后 should calculate correctly."""
        result = parse_time_reference("5天后交货", current_week=5, current_round=0, language="zh")
        assert result == {"scheduled_week": 6, "scheduled_round": 2}

    def test_zh_months_later(self):
        """X个月后 should calculate correctly."""
        result = parse_time_reference(
            "两个月后见面", current_week=5, current_round=0, language="zh"
        )
        assert result == {"scheduled_week": 13, "scheduled_round": 0}

    def test_en_this_weekend(self):
        """this weekend in English."""
        result = parse_time_reference(
            "this weekend", current_week=5, current_round=0, language="en"
        )
        assert result == {"scheduled_week": 5, "scheduled_round": 2}

    def test_en_next_week(self):
        """next week in English."""
        result = parse_time_reference("next week", current_week=5, current_round=0, language="en")
        assert result == {"scheduled_week": 6, "scheduled_round": 1}

    def test_en_tomorrow(self):
        """tomorrow in English."""
        result = parse_time_reference("tomorrow", current_week=5, current_round=0, language="en")
        assert result == {"scheduled_week": 5, "scheduled_round": 1}

    def test_en_days_later(self):
        """X days later in English."""
        result = parse_time_reference(
            "4 days later", current_week=5, current_round=0, language="en"
        )
        assert result == {"scheduled_week": 6, "scheduled_round": 1}

    def test_unknown_returns_none(self):
        """Unknown time reference should return None."""
        result = parse_time_reference("sometime", current_week=5, current_round=0, language="en")
        assert result is None


class TestScheduledEventManagerContract:
    """Contract tests for ScheduledEventManager."""

    def test_add_event(self):
        """add_event should store event."""
        manager = ScheduledEventManager()
        event = ScheduledEvent(description="Test event")
        manager.add_event(event)
        assert len(manager.events) == 1

    def test_add_duplicate_ignored(self):
        """Adding duplicate event_id should be ignored."""
        manager = ScheduledEventManager()
        event = ScheduledEvent(event_id="same", description="First")
        manager.add_event(event)
        dup = ScheduledEvent(event_id="same", description="Second")
        manager.add_event(dup)
        assert len(manager.events) == 1

    def test_remove_event(self):
        """remove_event should delete by ID."""
        manager = ScheduledEventManager()
        event = ScheduledEvent(event_id="to_remove", description="Test")
        manager.add_event(event)
        assert manager.remove_event("to_remove") is True
        assert len(manager.events) == 0

    def test_remove_nonexistent(self):
        """remove_event for unknown ID should return False."""
        manager = ScheduledEventManager()
        assert manager.remove_event("nope") is False

    def test_get_pending_events_for_round(self):
        """Should return pending events matching time."""
        manager = ScheduledEventManager()
        e1 = ScheduledEvent(
            scheduled_week=5, scheduled_round=1, importance="critical", status="pending"
        )
        e2 = ScheduledEvent(
            scheduled_week=5, scheduled_round=1, importance="normal", status="pending"
        )
        e3 = ScheduledEvent(
            scheduled_week=5, scheduled_round=2, importance="critical", status="pending"
        )
        manager.add_event(e1)
        manager.add_event(e2)
        manager.add_event(e3)

        pending = manager.get_pending_events_for_round(5, 1)
        assert len(pending) == 2
        # critical should come first
        assert pending[0].importance == "critical"

    def test_get_overdue_events(self):
        """Should return overdue pending events."""
        manager = ScheduledEventManager()
        e1 = ScheduledEvent(scheduled_week=3, scheduled_round=0, status="pending")
        e2 = ScheduledEvent(scheduled_week=10, scheduled_round=0, status="pending")
        manager.add_event(e1)
        manager.add_event(e2)

        overdue = manager.get_overdue_events(5, 0)
        assert len(overdue) == 1
        assert overdue[0].scheduled_week == 3

    def test_mark_triggered(self):
        """mark_triggered should update status."""
        manager = ScheduledEventManager()
        event = ScheduledEvent(event_id="e1", status="pending")
        manager.add_event(event)
        manager.mark_triggered("e1")
        assert manager.events[0].status == "triggered"

    def test_mark_skipped(self):
        """mark_skipped should update status."""
        manager = ScheduledEventManager()
        event = ScheduledEvent(event_id="e1", status="pending")
        manager.add_event(event)
        manager.mark_skipped("e1")
        assert manager.events[0].status == "skipped"

    def test_merge_events(self):
        """merge_events should create merged event and mark originals."""
        manager = ScheduledEventManager()
        e1 = ScheduledEvent(
            event_id="a",
            description="Meeting",
            parties=["Alice"],
            scheduled_week=5,
            scheduled_round=1,
        )
        e2 = ScheduledEvent(
            event_id="b",
            description="Dinner",
            parties=["Alice", "Bob"],
            scheduled_week=5,
            scheduled_round=1,
        )
        manager.add_event(e1)
        manager.add_event(e2)

        merged = manager.merge_events(e1, e2)
        assert "Meeting" in merged.description
        assert "Dinner" in merged.description
        assert set(merged.parties) == {"Alice", "Bob"}
        assert e1.status == "merged"
        assert e2.status == "merged"

    def test_cleanup_old_events(self):
        """cleanup_old_events should remove old processed events."""
        manager = ScheduledEventManager()
        e1 = ScheduledEvent(event_id="old", scheduled_week=1, status="triggered")
        e2 = ScheduledEvent(event_id="recent", scheduled_week=10, status="triggered")
        manager.add_event(e1)
        manager.add_event(e2)

        count = manager.cleanup_old_events(current_week=15, keep_weeks=5)
        assert count == 1
        assert len(manager.events) == 1

    def test_to_dict_list_roundtrip(self):
        """to_dict_list and from_dict_list should be inverse."""
        manager = ScheduledEventManager()
        event = ScheduledEvent(description="Test", scheduled_week=5)
        manager.add_event(event)

        data = manager.to_dict_list()
        restored = ScheduledEventManager.from_dict_list(data)
        assert len(restored.events) == 1
        assert restored.events[0].description == "Test"
