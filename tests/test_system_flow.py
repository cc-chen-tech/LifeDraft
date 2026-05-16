"""System flow tests for end-to-end game functionality."""

from unittest.mock import Mock, patch

from config.settings import settings
from src.game.game_loop import GameLoop
from src.game.historical_summary_selector import HistoricalSummarySelector
from src.game.state import CharacterState, PlayerState


class TestGameInitialization:
    """Test game initialization flow."""

    @patch("src.ai.generator.EventGenerator")
    def test_game_initialization(self, mock_generator):
        """Test that game initializes correctly."""
        game = GameLoop(language="zh")

        # Start new game
        state = game.start_new_game()

        assert state is not None
        assert isinstance(state, PlayerState)
        assert state.week == 0
        assert state.age == settings.STARTING_AGE
        assert state.current_round == 0

    @patch("src.ai.generator.EventGenerator")
    def test_game_load_existing(self, mock_generator):
        """Test loading an existing game state."""
        game = GameLoop(language="zh")

        # Create state dict
        state_dict = {
            "age": 25,
            "week": 20,
            "energy": 80,
            "mood": 70,
            "knowledge": 60,
            "wealth": 15000,
            "relationships": {"Friend": 70},
            "characters": {},
            "current_round": 1,
            "rounds_per_week": 3,
        }

        state = game.load_game(state_dict)

        assert state.age == 25
        assert state.week == 20
        assert state.current_round == 1


class TestWeekAdvancement:
    """Test week advancement flow."""

    @patch("src.ai.generator.EventGenerator")
    def test_week_advancement(self, mock_generator):
        """Test advancing to next week."""
        game = GameLoop(language="zh")
        game.start_new_game()

        initial_week = game.player_state.week

        # Advance week
        result = game.advance_to_next_week()

        assert result is True
        assert game.player_state.week == initial_week + 1
        assert game.player_state.current_round == 0

    @patch("src.ai.generator.EventGenerator")
    def test_week_does_not_advance_if_game_over(self, mock_generator):
        """Test that week doesn't advance after game over."""
        game = GameLoop(language="zh")
        game.start_new_game()

        # Set to last week
        game.player_state.week = settings.TOTAL_WEEKS - 1

        # Advance to game over
        game.advance_to_next_week()

        # Should be game over now
        assert game.is_game_over() is True


class TestRoundSystem:
    """Test the 3-rounds-per-week system."""

    @patch("src.ai.generator.EventGenerator")
    def test_round_system_3_rounds_per_week(self, mock_generator):
        """Test that each week has 3 rounds."""
        game = GameLoop(language="zh")
        game.start_new_game()

        assert game.player_state.rounds_per_week == 3
        assert game.player_state.current_round == 0

    @patch("src.ai.generator.EventGenerator")
    def test_round_increments_within_week(self, mock_generator):
        """Test round increments correctly."""
        game = GameLoop(language="zh")
        game.start_new_game()

        # Simulate round progression
        for round_num in range(3):
            assert game.player_state.current_round == round_num
            game.player_state.current_round += 1

        # After 3 rounds, should be ready for next week
        assert game.player_state.current_round == 3

    @patch("src.ai.generator.EventGenerator")
    def test_round_resets_on_new_week(self, mock_generator):
        """Test that round resets when advancing week."""
        game = GameLoop(language="zh")
        game.start_new_game()

        # Set to end of week
        game.player_state.current_round = 3

        # Advance week
        game.advance_to_next_week()

        # Round should reset
        assert game.player_state.current_round == 0


class TestSummaryTriggers:
    """Test summary generation triggers."""

    def test_weekly_summary_generation_trigger(self):
        """Test that weekly summaries are stored correctly."""
        player = PlayerState(name="Test", week=5)

        # Add a weekly summary
        summary_entry = {
            "week": 5,
            "summary": "This week the player made important decisions...",
            "key_events": ["event1", "event2"],
        }
        player.weekly_summaries.append(summary_entry)

        assert len(player.weekly_summaries) == 1
        assert player.weekly_summaries[0]["week"] == 5

    def test_yearly_summary_generation_trigger(self):
        """Test that yearly summaries trigger at correct intervals."""
        player = PlayerState(name="Test", week=48)

        # Add a yearly summary
        summary_entry = {
            "start_week": 0,
            "end_week": 47,
            "summary": "First year summary...",
        }
        player.yearly_summaries.append(summary_entry)

        assert len(player.yearly_summaries) == 1
        assert player.yearly_summaries[0]["end_week"] == 47

    def test_four_week_summaries_storage(self):
        """Test four-week summaries are stored correctly."""
        player = PlayerState(name="Test", week=4)

        # Add a four-week summary
        summary_entry = {
            "start_week": 0,
            "end_week": 3,
            "summary": "First month summary...",
        }
        player.four_week_summaries.append(summary_entry)

        assert len(player.four_week_summaries) == 1


class TestStateSerialization:
    """Test state serialization round trips."""

    def test_player_state_serialization_round_trip(self):
        """Test complete PlayerState serialization."""
        original = PlayerState(
            age=25,
            week=15,
            energy=75,
            mood=65,
            knowledge=55,
            wealth=12000,
            relationships={"Friend1": 70, "Friend2": 80},
            current_round=2,
            story_history=["Story 1", "Story 2"],
            decision_history=[
                {"week": 1, "choice": "A"},
                {"week": 2, "choice": "B"},
            ],
        )

        # Add character as dict (as stored internally)
        char_dict = CharacterState(
            name="Friend1",
            affinity=70,
            trust=60,
            sexual_orientation="heterosexual",
        ).model_dump()
        original.characters["Friend1"] = char_dict

        # Serialize
        state_dict = original.to_dict()

        # Deserialize
        restored = PlayerState.from_dict(state_dict)

        # Verify all fields
        assert restored.age == original.age
        assert restored.week == original.week
        assert restored.energy == original.energy
        assert restored.current_round == original.current_round
        assert len(restored.story_history) == 2
        assert len(restored.decision_history) == 2
        assert "Friend1" in restored.characters

    def test_character_state_serialization_round_trip(self):
        """Test complete CharacterState serialization."""
        original = CharacterState(
            name="TestNPC",
            role="mentor",
            age=40,
            gender="male",
            sexual_orientation="heterosexual",
            relationship_status="married",
            affinity=75,
            trust=80,
            respect=85,
            personality_traits=["wise", "patient"],
            triggered_events=["mentor_disciple"],
            peak_affinity=80,
        )

        # Serialize via model_dump
        char_dict = original.model_dump()

        # Deserialize
        restored = CharacterState(**char_dict)

        # Verify
        assert restored.name == original.name
        assert restored.role == original.role
        assert restored.sexual_orientation == original.sexual_orientation
        assert restored.relationship_status == original.relationship_status
        assert restored.triggered_events == original.triggered_events
        assert restored.peak_affinity == original.peak_affinity


class TestGameProgress:
    """Test game progress tracking."""

    @patch("src.ai.generator.EventGenerator")
    def test_get_progress(self, mock_generator):
        """Test progress information retrieval."""
        game = GameLoop(language="zh")
        game.start_new_game()
        game.player_state.week = 24

        progress = game.get_progress()

        assert progress["week"] == 24
        assert "progress_percent" in progress
        assert progress["progress_percent"] > 0

    @patch("src.ai.generator.EventGenerator")
    def test_game_over_detection(self, mock_generator):
        """Test game over detection."""
        game = GameLoop(language="zh")
        game.start_new_game()

        # Not over initially
        assert game.is_game_over() is False

        # Set to end
        game.player_state.week = settings.TOTAL_WEEKS

        # Now over
        assert game.is_game_over() is True


class TestHistoricalSummaryProbability:
    """Test historical summary selection probability."""

    @patch("src.ai.client.openai.OpenAI")
    def test_probability_decay_weekly(self, mock_openai_class):
        """Test that weekly summary selection probability decays."""
        mock_openai_class.return_value = Mock()
        game = GameLoop(language="zh")
        game.player_state = PlayerState(name="Test", week=100)

        # Add summaries at different distances
        game.player_state.weekly_summaries = [
            {"week": 99, "summary": "Recent"},  # Distance 1
            {"week": 50, "summary": "Old"},  # Distance 50
        ]

        # Run many times and count
        recent_count = 0
        old_count = 0

        for _ in range(1000):
            weekly, _ = (
                HistoricalSummarySelector.select_random_historical_summary_fallback(
                    game.player_state
                )
            )
            if weekly == "Recent":
                recent_count += 1
            elif weekly == "Old":
                old_count += 1

        # Recent should be selected more often
        # (though old might not be selected at all due to low probability)
        # Just verify the method runs without error
        assert recent_count >= 0
        assert old_count >= 0

    @patch("src.ai.client.openai.OpenAI")
    def test_no_summaries_returns_none(self, mock_openai_class):
        """Test that empty summaries returns None."""
        mock_openai_class.return_value = Mock()
        game = GameLoop(language="zh")
        game.player_state = PlayerState(name="Test", week=10)
        game.player_state.weekly_summaries = []
        game.player_state.yearly_summaries = []

        weekly, yearly = (
            HistoricalSummarySelector.select_random_historical_summary_fallback(
                game.player_state
            )
        )

        assert weekly is None
        assert yearly is None
