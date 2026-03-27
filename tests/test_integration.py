"""Integration tests for module interactions."""

from unittest.mock import Mock, patch

import pytest

# Integration tests - module interactions
pytestmark = pytest.mark.integration

from src.game.character_creation import assign_sexual_orientation
from src.game.game_loop import GameLoop
from src.game.historical_summary_selector import HistoricalSummarySelector
from src.game.state import CharacterState, PlayerState
from src.mcp.relationship_service import RelationshipMCPService


class TestCharacterCreationIntegration:
    """Test character creation integration with game state."""

    def test_character_has_hidden_attrs_after_creation(self):
        """Test that created characters have hidden attributes."""
        # Create a character with hidden attributes
        char = CharacterState(
            name="TestNPC",
            gender="female",
            sexual_orientation=assign_sexual_orientation(),
        )

        # Verify hidden attributes exist
        assert hasattr(char, "sexual_orientation")
        assert char.sexual_orientation in [
            "heterosexual",
            "homosexual",
            "bisexual",
            "asexual",
        ]
        assert hasattr(char, "relationship_status")
        assert hasattr(char, "peak_affinity")
        assert hasattr(char, "triggered_events")

    def test_player_state_characters_sync(self):
        """Test that PlayerState.characters stores CharacterState correctly."""
        player = PlayerState(name="Player")

        # Add a character
        char = CharacterState(
            name="Friend",
            role="roommate",
            affinity=60,
            trust=55,
        )
        player.characters["Friend"] = char

        # Verify sync
        assert "Friend" in player.characters
        assert player.characters["Friend"].affinity == 60

        # Update character
        player.characters["Friend"].affinity = 75
        assert player.characters["Friend"].affinity == 75

    def test_relationships_dict_syncs_with_characters(self):
        """Test that relationships dict stays in sync with characters."""
        player = PlayerState(name="Player")

        # Add character
        char = CharacterState(name="Friend", affinity=70)
        player.characters["Friend"] = char

        # Manually sync (as game loop does)
        player.relationships["Friend"] = char.affinity

        assert player.relationships["Friend"] == 70


class TestRelationshipEventIntegration:
    """Test relationship event system integration."""

    def test_relationship_event_trigger_flow(self):
        """Test complete relationship event trigger flow."""
        service = RelationshipMCPService(
            player_gender="male", player_orientation="heterosexual"
        )

        # Create player with compatible character
        player = PlayerState()
        player.character_settings = {"gender": {"gender": "male"}}
        char = CharacterState(
            name="Love Interest",
            gender="female",
            sexual_orientation="heterosexual",
            relationship_status="single",
            affinity=80,
            trust=70,
        )
        player.characters["Love Interest"] = char

        # Get triggered events
        events = service.get_triggered_events(player, era="modern", max_events=5)

        # Should detect romance_spark
        event_types = [e["event_type"] for e in events]
        assert "romance_spark" in event_types

        # Mark as triggered
        service.mark_event_triggered(player, "Love Interest", "romance_spark")

        # Verify marked
        assert "romance_spark" in player.characters["Love Interest"].triggered_events

        # Should not trigger again
        events_again = service.get_triggered_events(player, era="modern", max_events=5)
        event_types_again = [e["event_type"] for e in events_again]
        assert "romance_spark" not in event_types_again

    def test_romance_event_requires_orientation_match(self):
        """Test that romance events require orientation compatibility."""
        service = RelationshipMCPService(
            player_gender="male", player_orientation="heterosexual"
        )

        # Create incompatible character (same gender, both hetero)
        player = PlayerState()
        player.character_settings = {"gender": {"gender": "male"}}
        char = CharacterState(
            name="Colleague",
            gender="male",
            sexual_orientation="heterosexual",
            relationship_status="single",
            affinity=90,  # High affinity
            trust=80,
        )
        player.characters["Colleague"] = char

        # Get triggered events
        events = service.get_triggered_events(player, era="modern", max_events=5)

        # Should NOT detect romance events
        event_types = [e["event_type"] for e in events]
        assert "romance_spark" not in event_types
        assert "marriage_proposal" not in event_types

    def test_negative_event_trigger_conditions(self):
        """Test negative events trigger with low affinity and high peak."""
        service = RelationshipMCPService()

        player = PlayerState()
        char = CharacterState(
            name="Ex-Friend",
            affinity=15,  # Low current affinity
            trust=20,
            peak_affinity=80,  # Was once close
        )
        player.characters["Ex-Friend"] = char

        # Get triggered events
        events = service.get_triggered_events(player, era="modern", max_events=5)

        # Should detect become_enemy
        event_types = [e["event_type"] for e in events]
        assert "become_enemy" in event_types


class TestGameLoopIntegration:
    """Test game loop integration with other modules."""

    @patch("src.ai.generator.EventGenerator")
    def test_game_loop_initializes_relationship_service(self, mock_generator):
        """Test that GameLoop initializes RelationshipMCPService."""
        game = GameLoop(language="zh")

        assert hasattr(game, "relationship_service")
        assert isinstance(game.relationship_service, RelationshipMCPService)

    @patch("src.ai.client.openai.OpenAI")
    def test_game_loop_historical_summary_selection(self, mock_openai_class):
        """Test historical summary selection in game loop."""
        mock_openai_class.return_value = Mock()
        game = GameLoop(language="zh")
        game.player_state = PlayerState(week=50)

        # Add some historical summaries with content that matches keywords
        game.player_state.weekly_summaries = [
            {"week": 48, "summary": "Week 48 summary about 项目进展"},
            {"week": 40, "summary": "Week 40 summary about 工作变化"},
        ]
        game.player_state.yearly_summaries = [
            {"end_week": 48, "summary": "Year 1 summary about 项目进展"},
        ]

        # Test the fallback random path (no keywords context)
        # HistoricalSummarySelector.select_relevant_historical_summary falls back to
        # select_random_historical_summary_fallback when no keywords
        found_weekly = False
        found_yearly = False

        for _ in range(2000):
            weekly, yearly = (
                HistoricalSummarySelector.select_random_historical_summary_fallback(
                    game.player_state
                )
            )
            if weekly:
                found_weekly = True
            if yearly:
                found_yearly = True
            if found_weekly and found_yearly:
                break

        # Should find at least weekly (higher probability at short distance)
        assert found_weekly is True


class TestStateSerializationIntegration:
    """Test state serialization integration."""

    def test_player_state_with_characters_serialization(self):
        """Test PlayerState serialization with CharacterState."""
        player = PlayerState(age=25, week=10)

        # Add characters as dicts (as stored internally)
        char1_dict = CharacterState(
            name="Friend1",
            gender="female",
            sexual_orientation="bisexual",
            affinity=70,
            triggered_events=["deep_friendship"],
        ).model_dump()
        char2_dict = CharacterState(
            name="Friend2",
            gender="male",
            sexual_orientation="heterosexual",
            affinity=80,
            trust=75,
        ).model_dump()
        player.characters["Friend1"] = char1_dict
        player.characters["Friend2"] = char2_dict

        # Serialize
        state_dict = player.to_dict()

        # Deserialize
        restored = PlayerState.from_dict(state_dict)

        # Verify
        assert restored.age == 25
        assert "Friend1" in restored.characters
        assert restored.characters["Friend1"]["sexual_orientation"] == "bisexual"
        assert "deep_friendship" in restored.characters["Friend1"]["triggered_events"]
        assert restored.characters["Friend2"]["trust"] == 75
