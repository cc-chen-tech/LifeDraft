"""Fallback event generation contract tests.

No mocks. Tests pure logic event generation.
"""

from src.ai.models import GameEvent
from src.game.fallback_events import (generate_fallback_event,
                                      generate_simple_round_event,
                                      generate_simple_scheduled_event)
import pytest

pytestmark = [pytest.mark.unit]



class TestFallbackEventsContract:
    """Contract tests for fallback event generation."""

    def test_generate_fallback_event_zh_basic(self):
        """Basic zh fallback event should have correct structure."""
        event = generate_fallback_event(language="zh", is_round=False)

        assert isinstance(event, GameEvent)
        assert "平静的一周" in event.event_description
        assert len(event.options) == 2

    def test_generate_fallback_event_en_basic(self):
        """Basic en fallback event should have correct structure."""
        event = generate_fallback_event(language="en", is_round=False)

        assert isinstance(event, GameEvent)
        assert "quiet week" in event.event_description
        assert len(event.options) == 2

    def test_generate_fallback_event_zh_round(self):
        """Round-specific zh fallback should include day name."""
        event = generate_fallback_event(language="zh", is_round=True, current_round=0)

        assert "周一" in event.event_description
        assert len(event.options) == 2

    def test_generate_fallback_event_en_round(self):
        """Round-specific en fallback should include day name."""
        event = generate_fallback_event(language="en", is_round=True, current_round=0)

        assert "Monday" in event.event_description
        assert len(event.options) == 2

    def test_generate_fallback_event_round_names_cycle(self):
        """Round names should cycle for indices 0, 1, 2."""
        e0 = generate_fallback_event(language="zh", is_round=True, current_round=0)
        e1 = generate_fallback_event(language="zh", is_round=True, current_round=1)
        e2 = generate_fallback_event(language="zh", is_round=True, current_round=2)

        assert "周一" in e0.event_description
        assert "周中" in e1.event_description
        assert "周末" in e2.event_description

    def test_generate_fallback_event_round_index_out_of_range(self):
        """Round index out of range should use fallback name."""
        event = generate_fallback_event(language="zh", is_round=True, current_round=10)

        assert "Round 10" in event.event_description

    def test_fallback_event_options_have_effects(self):
        """Fallback event options should have expected effects."""
        event = generate_fallback_event(language="zh", is_round=False)

        opt0 = event.options[0]
        assert "mood" in opt0.effects
        assert opt0.effects["mood"] == 5

        opt1 = event.options[1]
        assert "knowledge" in opt1.effects
        assert opt1.effects["knowledge"] == 5

    def test_generate_simple_round_event_zh(self):
        """Simple round event zh should have 3 options."""
        event = generate_simple_round_event(language="zh", current_round=0)

        assert isinstance(event, GameEvent)
        assert "平静的日子" in event.event_description
        assert len(event.options) == 3

    def test_generate_simple_round_event_en(self):
        """Simple round event en should have 3 options."""
        event = generate_simple_round_event(language="en", current_round=0)

        assert "quiet day" in event.event_description.lower()
        assert len(event.options) == 3

    def test_generate_simple_scheduled_event_zh(self):
        """Scheduled event zh should include descriptions."""
        events = [{"description": "还债"}, {"description": "探望母亲"}]
        event = generate_simple_scheduled_event(language="zh", scheduled_events=events)

        assert isinstance(event, GameEvent)
        assert "还债" in event.event_description
        assert "探望母亲" in event.event_description
        assert len(event.options) == 3

    def test_generate_simple_scheduled_event_empty(self):
        """Scheduled event with no scheduled_events should still work."""
        event = generate_simple_scheduled_event(language="zh", scheduled_events=[])

        assert isinstance(event, GameEvent)
        assert len(event.options) == 3

    def test_generate_simple_scheduled_event_en(self):
        """Scheduled event en should work."""
        events = [{"description": "Pay debt"}]
        event = generate_simple_scheduled_event(language="en", scheduled_events=events)

        assert "Pay debt" in event.event_description

    def test_scheduled_event_option_effects(self):
        """Scheduled event options should have correct effects."""
        event = generate_simple_scheduled_event(language="zh", scheduled_events=[])

        serious = event.options[0]
        assert serious.effects.get("mood") == 10
        assert serious.effects.get("energy") == -10

        lazy = event.options[1]
        assert lazy.effects.get("mood") == -5

        delay = event.options[2]
        assert delay.effects.get("mood") == -15
