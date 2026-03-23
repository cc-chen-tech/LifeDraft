"""Tests for relationship MCP service."""

import pytest

from src.game.relationship_events import get_event_by_type
from src.game.state import CharacterState, PlayerState
from src.mcp.relationship_service import RelationshipMCPService, TriggeredEvent


class TestRomanceCompatibility:
    """Test romance compatibility logic."""

    def test_heterosexual_compatibility(self):
        """Test heterosexual compatibility (different genders)."""
        service = RelationshipMCPService(
            player_gender="male", player_orientation="heterosexual"
        )

        # Male player (hetero) + Female NPC (hetero) = compatible
        assert service.is_romance_compatible("heterosexual", "female") is True

        # Male player (hetero) + Male NPC (hetero) = not compatible
        assert service.is_romance_compatible("heterosexual", "male") is False

        # Male player (hetero) + Female NPC (homo) = not compatible
        assert service.is_romance_compatible("homosexual", "female") is False

    def test_homosexual_compatibility(self):
        """Test homosexual compatibility (same gender)."""
        service = RelationshipMCPService(
            player_gender="male", player_orientation="homosexual"
        )

        # Male player (homo) + Male NPC (homo) = compatible
        assert service.is_romance_compatible("homosexual", "male") is True

        # Male player (homo) + Female NPC (homo) = not compatible
        assert service.is_romance_compatible("homosexual", "female") is False

    def test_bisexual_compatibility(self):
        """Test bisexual compatibility (flexible)."""
        service = RelationshipMCPService(
            player_gender="male", player_orientation="bisexual"
        )

        # Bisexual is compatible with multiple orientations
        assert service.is_romance_compatible("bisexual", "female") is True
        assert service.is_romance_compatible("bisexual", "male") is True
        assert service.is_romance_compatible("heterosexual", "female") is True
        assert service.is_romance_compatible("homosexual", "male") is True

    def test_asexual_never_compatible(self):
        """Test asexual is never romantically compatible."""
        service = RelationshipMCPService(
            player_gender="male", player_orientation="heterosexual"
        )

        # Asexual NPC is not compatible
        assert service.is_romance_compatible("asexual", "female") is False
        assert service.is_romance_compatible("asexual", "male") is False

        # Asexual player is not compatible
        service_asexual = RelationshipMCPService(
            player_gender="male", player_orientation="asexual"
        )
        assert service_asexual.is_romance_compatible("heterosexual", "female") is False


class TestEventConditionChecking:
    """Test event condition checking."""

    def test_check_romance_spark_conditions(self):
        """Test romance_spark event conditions."""
        service = RelationshipMCPService(
            player_gender="male", player_orientation="heterosexual"
        )

        # Create compatible character
        char = CharacterState(
            name="TestNPC",
            gender="female",
            sexual_orientation="heterosexual",
            relationship_status="single",
            affinity=80,  # Above threshold (75)
            trust=70,
        )

        player = PlayerState()
        player.characters = {"TestNPC": char}

        event_def = get_event_by_type("romance_spark")

        # Should meet conditions
        result = service.check_event_conditions(event_def, char, player)
        assert result is True

    def test_check_romance_spark_fails_low_affinity(self):
        """Test romance_spark fails with low affinity."""
        service = RelationshipMCPService(
            player_gender="male", player_orientation="heterosexual"
        )

        char = CharacterState(
            name="TestNPC",
            gender="female",
            sexual_orientation="heterosexual",
            relationship_status="single",
            affinity=50,  # Below threshold (75)
        )

        player = PlayerState()
        player.characters = {"TestNPC": char}

        event_def = get_event_by_type("romance_spark")

        # Should NOT meet conditions
        result = service.check_event_conditions(event_def, char, player)
        assert result is False

    def test_check_romance_spark_fails_wrong_orientation(self):
        """Test romance_spark fails with incompatible orientation."""
        service = RelationshipMCPService(
            player_gender="male", player_orientation="heterosexual"
        )

        char = CharacterState(
            name="TestNPC",
            gender="male",  # Same gender
            sexual_orientation="heterosexual",  # Both hetero, same gender = incompatible
            relationship_status="single",
            affinity=80,
        )

        player = PlayerState()
        player.characters = {"TestNPC": char}

        event_def = get_event_by_type("romance_spark")

        # Should NOT meet conditions
        result = service.check_event_conditions(event_def, char, player)
        assert result is False

    def test_check_become_enemy_conditions(self):
        """Test become_enemy event conditions (negative threshold)."""
        service = RelationshipMCPService()

        char = CharacterState(
            name="TestNPC",
            affinity=15,  # Low affinity
            peak_affinity=80,  # Was once close
        )

        player = PlayerState()
        player.characters = {"TestNPC": char}

        event_def = get_event_by_type("become_enemy")

        # Should meet conditions (low affinity, high peak)
        result = service.check_event_conditions(event_def, char, player)
        assert result is True

    def test_check_become_enemy_fails_no_history(self):
        """Test become_enemy fails if never had good relationship."""
        service = RelationshipMCPService()

        char = CharacterState(
            name="TestNPC",
            affinity=15,
            peak_affinity=30,  # Never had high affinity
        )

        player = PlayerState()
        player.characters = {"TestNPC": char}

        event_def = get_event_by_type("become_enemy")

        # Should NOT meet conditions (no history of good relationship)
        result = service.check_event_conditions(event_def, char, player)
        assert result is False


class TestEventTriggering:
    """Test event triggering and marking."""

    def test_mark_event_triggered(self):
        """Test marking an event as triggered."""
        service = RelationshipMCPService()

        char = CharacterState(name="TestNPC")
        player = PlayerState()
        player.characters = {"TestNPC": char}

        # Initially no triggered events
        assert "romance_spark" not in char.triggered_events

        # Mark event as triggered
        result = service.mark_event_triggered(player, "TestNPC", "romance_spark")
        assert result is True

        # Verify it's marked
        assert "romance_spark" in player.characters["TestNPC"].triggered_events

    def test_triggered_events_not_repeat(self):
        """Test that triggered events don't repeat."""
        service = RelationshipMCPService(
            player_gender="male", player_orientation="heterosexual"
        )

        char = CharacterState(
            name="TestNPC",
            gender="female",
            sexual_orientation="heterosexual",
            relationship_status="single",
            affinity=80,
            trust=70,
            triggered_events=["romance_spark"],  # Already triggered
        )

        player = PlayerState()
        player.character_settings = {"gender": {"gender": "male"}}
        player.characters = {"TestNPC": char}

        # Get triggered events
        events = service.get_triggered_events(player, era="modern", max_events=5)

        # romance_spark should not appear (already triggered)
        event_types = [e["event_type"] for e in events]
        assert "romance_spark" not in event_types

    def test_get_triggered_events_respects_max(self):
        """Test that get_triggered_events respects max_events."""
        service = RelationshipMCPService(
            player_gender="male", player_orientation="heterosexual"
        )

        # Create multiple characters that could trigger events
        player = PlayerState()
        player.character_settings = {"gender": {"gender": "male"}}

        for i in range(5):
            char = CharacterState(
                name=f"NPC{i}",
                gender="female",
                sexual_orientation="heterosexual",
                relationship_status="single",
                affinity=80,
                trust=70,
            )
            player.characters[f"NPC{i}"] = char

        # Get at most 2 events
        events = service.get_triggered_events(player, era="modern", max_events=2)

        assert len(events) <= 2


class TestTriggeredEvent:
    """Test TriggeredEvent dataclass."""

    def test_triggered_event_to_dict(self):
        """Test TriggeredEvent.to_dict()."""
        event_def = get_event_by_type("romance_spark")

        triggered = TriggeredEvent(
            event_type="romance_spark",
            character_name="TestNPC",
            event_def=event_def,
            era_name="开始约会",
            description="TestNPC与你开始了一段浪漫关系",
            priority=1,
        )

        result = triggered.to_dict()

        assert result["event_type"] == "romance_spark"
        assert result["character_name"] == "TestNPC"
        assert result["era_name"] == "开始约会"
        assert result["category"] == "romance"
        assert result["priority"] == 1


class TestEraAdaptation:
    """Test era-based event name adaptation in service."""

    def test_generate_event_context_modern(self):
        """Test event context generation for modern era."""
        service = RelationshipMCPService()

        events = [
            {
                "event_type": "romance_spark",
                "character_name": "TestNPC",
                "era_name": "开始约会",
                "description": "测试描述",
            }
        ]

        context = service.generate_event_context(events, "modern", "zh")

        assert "TestNPC" in context
        assert "开始约会" in context

    def test_generate_event_context_empty(self):
        """Test event context generation with no events."""
        service = RelationshipMCPService()

        context = service.generate_event_context([], "modern", "zh")

        assert context == ""
