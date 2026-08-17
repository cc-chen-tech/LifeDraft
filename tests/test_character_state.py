"""Tests for CharacterState (NPC attributes system)."""

from src.game.state import CharacterState
import pytest

pytestmark = [pytest.mark.unit]



class TestCharacterState:
    """Test CharacterState class."""

    def test_character_state_defaults(self):
        """Test default values for CharacterState."""
        char = CharacterState(name="TestNPC")

        # Basic info
        assert char.name == "TestNPC"
        assert char.role == ""
        assert char.age == 25
        assert char.gender == ""

        # Personality
        assert char.personality_traits == []
        assert char.temperament == "balanced"

        # Dynamic state
        assert char.mood == 60
        assert char.mood_stability == 70

        # Social
        assert char.social_status == "ordinary"
        assert char.influence == 30

        # Competence
        assert char.competence == 50

        # Relationship with player
        assert char.affinity == 50
        assert char.trust == 50
        assert char.respect == 50

    def test_hidden_attributes(self):
        """Test hidden attributes that are not exposed to users."""
        char = CharacterState(name="TestNPC")

        # Hidden attributes defaults
        assert char.sexual_orientation == "heterosexual"
        assert char.relationship_status == "single"
        assert char.romantic_interest == ""
        assert char.has_external_obstacle is False
        assert char.peak_affinity == 50

        # Test setting hidden attributes
        char.sexual_orientation = "bisexual"
        assert char.sexual_orientation == "bisexual"

        char.relationship_status = "dating"
        assert char.relationship_status == "dating"

        char.romantic_interest = "Player"
        assert char.romantic_interest == "Player"

    def test_hidden_attributes_all_orientations(self):
        """Test all valid sexual orientation values."""
        valid_orientations = ["heterosexual", "homosexual", "bisexual", "asexual"]

        for orientation in valid_orientations:
            char = CharacterState(name="Test", sexual_orientation=orientation)
            assert char.sexual_orientation == orientation

    def test_update_relationship_attributes(self):
        """Test updating relationship attributes."""
        char = CharacterState(name="TestNPC")

        # Update affinity
        char.affinity = 80
        assert char.affinity == 80

        # Update trust
        char.trust = 70
        assert char.trust == 70

        # Update respect
        char.respect = 60
        assert char.respect == 60

        # Test bounds (min)
        char.affinity = 0
        assert char.affinity == 0

        # Test bounds (max)
        char.affinity = 100
        assert char.affinity == 100

    def test_peak_affinity_tracking(self):
        """Test tracking of historical peak affinity."""
        char = CharacterState(name="TestNPC", affinity=50)

        # Initial peak should match affinity
        assert char.peak_affinity == 50

        # When affinity increases, peak should update
        char.affinity = 80
        char.peak_affinity = max(char.peak_affinity, char.affinity)
        assert char.peak_affinity == 80

        # When affinity decreases, peak should remain
        char.affinity = 30
        # Peak should NOT decrease
        assert char.peak_affinity == 80

    def test_triggered_events_list(self):
        """Test management of triggered events list."""
        char = CharacterState(name="TestNPC")

        # Initially empty
        assert char.triggered_events == []

        # Add triggered events
        char.triggered_events.append("romance_spark")
        assert "romance_spark" in char.triggered_events

        char.triggered_events.append("deep_friendship")
        assert len(char.triggered_events) == 2

        # Check for existing event
        assert "romance_spark" in char.triggered_events
        assert "betrayal" not in char.triggered_events

    def test_event_triggers_defaults(self):
        """Test default event trigger thresholds."""
        char = CharacterState(name="TestNPC")

        # Check some key thresholds
        assert char.event_triggers["romance_spark"] == 75
        assert char.event_triggers["marriage_proposal"] == 85
        assert char.event_triggers["breakup"] == 25
        assert char.event_triggers["deep_friendship"] == 80
        assert char.event_triggers["betrayal_risk"] == 15

    def test_interaction_tracking(self):
        """Test interaction count and timing."""
        char = CharacterState(name="TestNPC")

        # Initial values
        assert char.interaction_count == 0
        assert char.last_interaction_week == -1

        # Simulate interaction
        char.interaction_count += 1
        char.last_interaction_week = 5

        assert char.interaction_count == 1
        assert char.last_interaction_week == 5

    def test_character_state_serialization(self):
        """Test CharacterState can be converted to dict and back."""
        char = CharacterState(
            name="TestNPC",
            role="friend",
            age=30,
            gender="female",
            sexual_orientation="bisexual",
            affinity=75,
            trust=80,
            respect=65,
            triggered_events=["romance_spark"],
        )

        # Convert to dict
        char_dict = char.model_dump()

        assert char_dict["name"] == "TestNPC"
        assert char_dict["role"] == "friend"
        assert char_dict["sexual_orientation"] == "bisexual"
        assert char_dict["affinity"] == 75
        assert "romance_spark" in char_dict["triggered_events"]

        # Recreate from dict
        new_char = CharacterState(**char_dict)
        assert new_char.name == char.name
        assert new_char.sexual_orientation == char.sexual_orientation
        assert new_char.affinity == char.affinity

    def test_relationship_status_values(self):
        """Test various relationship status values."""
        valid_statuses = ["single", "dating", "engaged", "married", "divorced"]

        for status in valid_statuses:
            char = CharacterState(name="Test", relationship_status=status)
            assert char.relationship_status == status

    def test_social_status_values(self):
        """Test various social status values."""
        valid_statuses = ["student", "ordinary", "professional", "leader", "elite"]

        for status in valid_statuses:
            char = CharacterState(name="Test", social_status=status)
            assert char.social_status == status

    def test_temperament_values(self):
        """Test various temperament values."""
        valid_temperaments = [
            "sanguine",
            "choleric",
            "melancholic",
            "phlegmatic",
            "balanced",
        ]

        for temp in valid_temperaments:
            char = CharacterState(name="Test", temperament=temp)
            assert char.temperament == temp
