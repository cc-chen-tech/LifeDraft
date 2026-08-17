"""CharacterState contract tests.

No mocks. Pure logic tests for NPC character state.
"""

from src.game.state.character_state import CharacterState
import pytest

pytestmark = [pytest.mark.unit]



class TestCharacterStateContract:
    """Contract tests for CharacterState."""

    def test_default_values(self):
        char = CharacterState(name="Test")
        assert char.affinity == 50
        assert char.trust == 50
        assert char.respect == 50
        assert char.mood == 60
        assert char.interaction_count == 0

    def test_update_mood_positive(self):
        char = CharacterState(name="Test", mood=50, mood_stability=0)
        char.update_mood(10)
        assert char.mood == 60

    def test_update_mood_negative(self):
        char = CharacterState(name="Test", mood=50, mood_stability=0)
        char.update_mood(-20)
        assert char.mood == 30

    def test_update_mood_clamped_high(self):
        char = CharacterState(name="Test", mood=95, mood_stability=0)
        char.update_mood(10)
        assert char.mood == 100

    def test_update_mood_clamped_low(self):
        char = CharacterState(name="Test", mood=5, mood_stability=0)
        char.update_mood(-10)
        assert char.mood == 0

    def test_update_mood_stability_reduces_change(self):
        char = CharacterState(name="Test", mood=50, mood_stability=100)
        char.update_mood(10)
        # stability 100 means factor 1.0, adjusted_change = 10 * (1 - 0.5) = 5
        assert char.mood == 55

    def test_update_relationship_affinity(self):
        char = CharacterState(name="Test", affinity=50)
        char.update_relationship(affinity_change=10)
        assert char.affinity == 60

    def test_update_relationship_peak_affinity(self):
        char = CharacterState(name="Test", affinity=50, peak_affinity=50)
        char.update_relationship(affinity_change=20)
        assert char.peak_affinity == 70

    def test_update_relationship_trust(self):
        char = CharacterState(name="Test", trust=50)
        char.update_relationship(trust_change=-10)
        assert char.trust == 40

    def test_update_relationship_respect(self):
        char = CharacterState(name="Test", respect=50)
        char.update_relationship(respect_change=15)
        assert char.respect == 65

    def test_update_relationship_clamped(self):
        char = CharacterState(name="Test", affinity=95)
        char.update_relationship(affinity_change=10)
        assert char.affinity == 100

    def test_record_interaction(self):
        char = CharacterState(name="Test")
        char.record_interaction(week=5, summary="Met at cafe")
        assert char.interaction_count == 1
        assert char.last_interaction_week == 5
        assert "cafe" in char.relationship_history

    def test_record_interaction_appends(self):
        char = CharacterState(name="Test")
        char.record_interaction(week=5, summary="First")
        char.record_interaction(week=6, summary="Second")
        assert char.interaction_count == 2
        assert "First" in char.relationship_history
        assert "Second" in char.relationship_history

    def test_get_interaction_style_default(self):
        char = CharacterState(name="Test", temperament="balanced")
        style = char.get_interaction_style()
        assert "平和" in style

    def test_get_interaction_style_sanguine(self):
        char = CharacterState(name="Test", temperament="sanguine")
        style = char.get_interaction_style()
        assert "热情活泼" in style

    def test_get_interaction_style_mood_high(self):
        char = CharacterState(name="Test", mood=85)
        style = char.get_interaction_style()
        assert "心情愉悦" in style

    def test_get_interaction_style_mood_low(self):
        char = CharacterState(name="Test", mood=20)
        style = char.get_interaction_style()
        assert "情绪低落" in style

    def test_get_interaction_style_affinity_high(self):
        char = CharacterState(name="Test", affinity=85)
        style = char.get_interaction_style()
        assert "亲切友好" in style

    def test_to_context_string(self):
        char = CharacterState(
            name="Alice",
            role="同事",
            age=25,
            occupation="工程师",
            personality_traits=["外向", "理性"],
            specialty=["编程"],
            mood=70,
            affinity=60,
            trust=55,
            social_status="professional",
            influence=40,
            relationship_desc="好友",
        )
        ctx = char.to_context_string()
        assert "Alice" in ctx
        assert "工程师" in ctx
        assert "外向" in ctx
        assert "编程" in ctx

    def test_from_simple_dict(self):
        char = CharacterState.from_simple_dict(
            {
                "name": "Bob",
                "role": "邻居",
                "relationship": "熟人",
            }
        )
        assert char.name == "Bob"
        assert char.role == "邻居"
        assert char.relationship_desc == "熟人"
