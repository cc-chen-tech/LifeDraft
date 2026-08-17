"""Tests for game loop."""

from unittest.mock import patch

from src.game.game_loop import GameLoop
from src.game.state import PlayerState
import pytest

pytestmark = [pytest.mark.unit]



class TestGameLoop:
    """Test GameLoop class."""

    def test_start_new_game(self):
        """Test starting a new game."""
        with patch("src.ai.generator.EventGenerator"):
            game_loop = GameLoop(language="en")
            state = game_loop.start_new_game()

            assert isinstance(state, PlayerState)
            assert state.age == 22
            assert state.week == 0

    def test_load_game(self):
        """Test loading a game."""
        with patch("src.ai.generator.EventGenerator"):
            game_loop = GameLoop(language="en")
            state_dict = {
                "energy": 80,
                "mood": 70,
                "knowledge": 60,
                "wealth": 15000,
                "relationships": {},
                "age": 23,
                "week": 10,
                "action_points": 3,
                "decision_history": [],
            }

            state = game_loop.load_game(state_dict)
            assert state.age == 23
            assert state.week == 10

    def test_advance_week(self):
        """Test advancing to next week."""
        with patch("src.ai.generator.EventGenerator"):
            game_loop = GameLoop(language="en")
            game_loop.start_new_game()

            initial_week = game_loop.player_state.week
            result = game_loop.advance_to_next_week()

            assert result is True
            assert game_loop.player_state.week == initial_week + 1
            assert game_loop.player_state.current_round == 0  # Round resets

    def test_is_game_over(self):
        """Test game over detection."""
        with patch("src.ai.generator.EventGenerator"):
            game_loop = GameLoop(language="en")
            game_loop.start_new_game()

            assert game_loop.is_game_over() is False

            game_loop.player_state.week = 96
            assert game_loop.is_game_over() is True

    def test_get_progress(self):
        """Test getting progress information."""
        with patch("src.ai.generator.EventGenerator"):
            game_loop = GameLoop(language="en")
            game_loop.start_new_game()
            game_loop.player_state.week = 24

            progress = game_loop.get_progress()
            assert progress["week"] == 24
            assert progress["progress_percent"] > 0
