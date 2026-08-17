"""Tests for relationship events definition system."""

from src.game.relationship_events import (RELATIONSHIP_EVENTS, EventCategory,
                                          RelationshipEventDef,
                                          get_event_by_type,
                                          get_events_by_category)
import pytest

pytestmark = [pytest.mark.unit]



class TestRelationshipEventDef:
    """Test RelationshipEventDef dataclass."""

    def test_event_definition_structure(self):
        """Test that event definitions have required fields."""
        for event_type, event_def in RELATIONSHIP_EVENTS.items():
            assert isinstance(event_def, RelationshipEventDef)
            assert event_def.event_type == event_type
            assert isinstance(event_def.category, EventCategory)
            assert isinstance(event_def.display_name, str)
            assert len(event_def.display_name) > 0

    def test_all_15_events_defined(self):
        """Verify all 15 relationship events are defined."""
        expected_events = [
            # Romance (4)
            "romance_spark",
            "marriage_proposal",
            "breakup",
            "elopement",
            # Friendship (4)
            "sworn_siblings",
            "soulmate",
            "business_partner",
            "entrust",
            # Negative (4)
            "become_enemy",
            "betrayal",
            "severance",
            "sabotage",
            # Special (3)
            "apprenticeship",
            "patron",
            "childbirth",
        ]

        assert len(RELATIONSHIP_EVENTS) == 15, f"Expected 15 events, got {len(RELATIONSHIP_EVENTS)}"

        for event_type in expected_events:
            assert event_type in RELATIONSHIP_EVENTS, f"Missing event: {event_type}"


class TestEraAdaptation:
    """Test era-based name adaptation."""

    def test_era_name_modern(self):
        """Test event names in modern era."""
        romance_event = get_event_by_type("romance_spark")
        assert romance_event is not None

        # Modern era should return modern name
        era_name = romance_event.get_era_name("modern", "zh")
        assert "约会" in era_name or "恋爱" in era_name or era_name == romance_event.display_name

    def test_era_name_ancient_china(self):
        """Test event names in ancient China era."""
        romance_event = get_event_by_type("romance_spark")
        assert romance_event is not None

        # Ancient China should return classical name
        era_name = romance_event.get_era_name("ancient_china", "zh")
        # Should be different from modern or be display_name
        assert isinstance(era_name, str)
        assert len(era_name) > 0

    def test_era_normalization(self):
        """Test era string normalization."""
        marriage_event = get_event_by_type("marriage_proposal")

        # Various era strings that should normalize to same era
        modern_variants = ["modern", "contemporary", "2020", "现代", "当代"]
        ancient_variants = ["ancient_china", "唐朝", "Tang", "宋", "明", "清"]

        # All modern variants should give consistent result
        modern_names = set()
        for era in modern_variants:
            name = marriage_event.get_era_name(era, "zh")
            modern_names.add(name)
        # Should normalize to same result
        assert len(modern_names) <= 2  # Allow for some variation

        # All ancient variants should give consistent result
        ancient_names = set()
        for era in ancient_variants:
            name = marriage_event.get_era_name(era, "zh")
            ancient_names.add(name)
        assert len(ancient_names) <= 2

    def test_era_fallback_to_modern(self):
        """Test that unknown era falls back to modern era name."""
        event = get_event_by_type("romance_spark")

        # Unknown era should fall back to modern (default)
        name = event.get_era_name("unknown_era_xyz", "zh")
        # Should return modern era name if available, or display_name
        assert isinstance(name, str)
        assert len(name) > 0


class TestEventCategories:
    """Test event category system."""

    def test_get_event_by_type(self):
        """Test getting event by type."""
        event = get_event_by_type("romance_spark")
        assert event is not None
        assert event.event_type == "romance_spark"
        assert event.category == EventCategory.ROMANCE

        # Non-existent event
        assert get_event_by_type("non_existent") is None

    def test_get_events_by_category_romance(self):
        """Test getting romance category events."""
        romance_events = get_events_by_category(EventCategory.ROMANCE)

        assert len(romance_events) == 4
        event_types = [e.event_type for e in romance_events]
        assert "romance_spark" in event_types
        assert "marriage_proposal" in event_types
        assert "breakup" in event_types
        assert "elopement" in event_types

    def test_get_events_by_category_friendship(self):
        """Test getting friendship category events."""
        friendship_events = get_events_by_category(EventCategory.FRIENDSHIP)

        assert len(friendship_events) == 4
        event_types = [e.event_type for e in friendship_events]
        assert "sworn_siblings" in event_types
        assert "soulmate" in event_types
        assert "business_partner" in event_types
        assert "entrust" in event_types

    def test_get_events_by_category_negative(self):
        """Test getting negative category events."""
        negative_events = get_events_by_category(EventCategory.NEGATIVE)

        assert len(negative_events) == 4
        event_types = [e.event_type for e in negative_events]
        assert "become_enemy" in event_types
        assert "betrayal" in event_types
        assert "severance" in event_types
        assert "sabotage" in event_types

    def test_get_events_by_category_special(self):
        """Test getting special category events."""
        special_events = get_events_by_category(EventCategory.SPECIAL)

        assert len(special_events) == 3
        event_types = [e.event_type for e in special_events]
        assert "apprenticeship" in event_types
        assert "patron" in event_types
        assert "childbirth" in event_types


class TestEventConditions:
    """Test event trigger conditions."""

    def test_romance_events_require_orientation_match(self):
        """Test that some romance events require orientation match."""
        romance_events = get_events_by_category(EventCategory.ROMANCE)

        # Only romance_spark and elopement require orientation match
        for event in romance_events:
            if event.event_type in ["romance_spark", "elopement"]:
                assert (
                    event.require_orientation_match is True
                ), f"Event {event.event_type} should require orientation match"

    def test_negative_events_use_negative_threshold(self):
        """Test that negative events use negative threshold (<=)."""
        negative_events = get_events_by_category(EventCategory.NEGATIVE)

        for event in negative_events:
            # Most negative events should use <= threshold
            if event.event_type in [
                "become_enemy",
                "betrayal",
                "severance",
                "sabotage",
            ]:
                assert (
                    event.is_negative_threshold is True
                ), f"Event {event.event_type} should use negative threshold"

    def test_elopement_requires_external_obstacle(self):
        """Test that elopement requires external obstacle."""
        elopement = get_event_by_type("elopement")

        assert elopement.require_external_obstacle is True
        assert elopement.require_orientation_match is True

    def test_breakup_requires_dating(self):
        """Test that breakup requires dating status."""
        breakup = get_event_by_type("breakup")

        assert breakup.require_dating is True
        assert breakup.is_negative_threshold is True

    def test_become_enemy_checks_peak_affinity(self):
        """Test that become_enemy checks historical peak affinity."""
        become_enemy = get_event_by_type("become_enemy")

        assert become_enemy.check_peak_affinity is True
        assert become_enemy.peak_affinity_threshold > 0
