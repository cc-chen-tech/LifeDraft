"""Tests for event generation."""
import pytest
from unittest.mock import Mock, patch
from src.ai.generator import EventGenerator
from src.ai.models import GameEvent, EventOption


class TestEventGenerator:
    """Test EventGenerator class."""
    
    def test_event_option_model(self):
        """Test EventOption model."""
        option = EventOption(
            text="Test option",
            effects={"energy": -10, "mood": 5}
        )
        assert option.text == "Test option"
        assert option.effects["energy"] == -10
    
    def test_game_event_model(self):
        """Test GameEvent model."""
        event = GameEvent(
            event_description="Test event",
            options=[
                EventOption(text="Option A", effects={"energy": -10}),
                EventOption(text="Option B", effects={"energy": 10})
            ]
        )
        assert len(event.options) == 2
        assert event.event_description == "Test event"
    
    def test_game_event_from_json(self):
        """Test creating GameEvent from JSON."""
        json_str = '''{
            "event_description": "Test event",
            "options": [
                {"text": "Option A", "effects": {"energy": -10}},
                {"text": "Option B", "effects": {"energy": 10}}
            ]
        }'''
        
        event = GameEvent.from_json(json_str)
        assert event.event_description == "Test event"
        assert len(event.options) == 2
    
    @patch('src.ai.client.openai.OpenAI')
    def test_generate_event_mock(self, mock_openai_class):
        """Test event generation with mocked API."""
        # Mock API response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{
            "event_description": "A test event",
            "options": [
                {"text": "Option A", "effects": {"energy": -10, "action_points": -1}},
                {"text": "Option B", "effects": {"energy": 10, "action_points": -1}}
            ]
        }'''
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        generator = EventGenerator(api_key="test_key")
        # Override the AIClient's internal client for mocking
        generator.ai_client.client = mock_client
        
        player_state = {
            "age": 22,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
            "week": 0
        }
        
        event = generator.generate_event(player_state, language="en")
        assert isinstance(event, GameEvent)
        assert len(event.options) == 2
