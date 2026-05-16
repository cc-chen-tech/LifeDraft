"""RelationshipEvents contract tests.

No mocks. Pure logic tests for event definitions and lookups.
"""

from src.game.relationship_events import (EventCategory, RelationshipEventDef,
                                          get_all_event_types,
                                          get_event_by_type,
                                          get_events_by_category)


class TestRelationshipEventsContract:
    """Contract tests for relationship event system."""

    def test_get_event_by_type_romance_spark(self):
        """romance_spark should exist with correct category."""
        event = get_event_by_type("romance_spark")
        assert event is not None
        assert event.event_type == "romance_spark"
        assert event.category == EventCategory.ROMANCE
        assert event.display_name == "恋爱萌芽"

    def test_get_event_by_type_breakup(self):
        """breakup should have negative threshold."""
        event = get_event_by_type("breakup")
        assert event is not None
        assert event.category == EventCategory.ROMANCE
        assert event.is_negative_threshold is True
        assert event.required_affinity == 25

    def test_get_event_by_type_nonexistent(self):
        """Unknown event type should return None."""
        assert get_event_by_type("not_real") is None

    def test_get_events_by_category_romance(self):
        """Romance category should have 4 events."""
        events = get_events_by_category(EventCategory.ROMANCE)
        assert len(events) == 4
        assert all(e.category == EventCategory.ROMANCE for e in events)

    def test_get_events_by_category_friendship(self):
        """Friendship category should have 4 events."""
        events = get_events_by_category(EventCategory.FRIENDSHIP)
        assert len(events) == 4
        assert all(e.category == EventCategory.FRIENDSHIP for e in events)

    def test_get_events_by_category_negative(self):
        """Negative category should have 4 events."""
        events = get_events_by_category(EventCategory.NEGATIVE)
        assert len(events) == 4
        assert all(e.category == EventCategory.NEGATIVE for e in events)

    def test_get_events_by_category_special(self):
        """Special category should have 3 events."""
        events = get_events_by_category(EventCategory.SPECIAL)
        assert len(events) == 3
        assert all(e.category == EventCategory.SPECIAL for e in events)

    def test_get_all_event_types_count(self):
        """Total event types should be 15."""
        types = get_all_event_types()
        assert len(types) == 15

    def test_all_events_have_description_template(self):
        """Every event should have a non-empty description template."""
        for event_type in get_all_event_types():
            event = get_event_by_type(event_type)
            assert event is not None
            assert event.description_template
            assert "{character}" in event.description_template

    def test_all_events_have_era_variations(self):
        """Every event should have era variations defined."""
        for event_type in get_all_event_types():
            event = get_event_by_type(event_type)
            assert event is not None
            assert "modern" in event.era_variations

    def test_era_name_modern(self):
        """Era name for modern should be returned."""
        event = get_event_by_type("romance_spark")
        assert event.get_era_name("modern", "zh") == "开始约会"

    def test_era_name_ancient_china(self):
        """Era name for ancient_china should be returned."""
        event = get_event_by_type("marriage_proposal")
        assert event.get_era_name("ancient_china", "zh") == "成亲"

    def test_era_name_ancient_west(self):
        """Era name for ancient_west should be returned."""
        event = get_event_by_type("sworn_siblings")
        assert event.get_era_name("ancient_west", "zh") == "Blood oath"

    def test_era_name_unknown_fallback(self):
        """Unknown era normalizes to modern, which is in era_variations."""
        event = get_event_by_type("romance_spark")
        # _normalize_era maps unknown -> "modern", and "modern" is always present
        assert event.get_era_name("space_age", "zh") == event.era_variations["modern"]

    def test_normalize_era_modern_variants(self):
        """Modern era should be detected from various inputs."""
        event = get_event_by_type("romance_spark")
        assert event._normalize_era("modern") == "modern"
        assert event._normalize_era("Modern") == "modern"
        assert event._normalize_era("当代") == "modern"
        assert event._normalize_era("2020s") == "modern"

    def test_normalize_era_ancient_china_variants(self):
        """Ancient china should be detected from various inputs."""
        event = get_event_by_type("romance_spark")
        assert event._normalize_era("Tang") == "ancient_china"
        assert event._normalize_era("唐朝") == "ancient_china"
        assert event._normalize_era("ancient_china") == "ancient_china"
        assert event._normalize_era("战国") == "ancient_china"

    def test_normalize_era_ancient_west_variants(self):
        """Ancient west should be detected from various inputs."""
        event = get_event_by_type("romance_spark")
        assert event._normalize_era("medieval") == "ancient_west"
        assert event._normalize_era("罗马") == "ancient_west"

    def test_normalize_era_modern_early_variants(self):
        """Modern early should be detected from various inputs."""
        event = get_event_by_type("romance_spark")
        assert event._normalize_era("民国") == "modern_early"
        assert event._normalize_era("victorian") == "modern_early"

    def test_normalize_era_default(self):
        """Unknown era should default to modern."""
        event = get_event_by_type("romance_spark")
        assert event._normalize_era("") == "modern"
        assert event._normalize_era("unknown") == "modern"

    def test_event_threshold_direction_positive(self):
        """Romance spark should require affinity >= 75."""
        event = get_event_by_type("romance_spark")
        assert event.required_affinity == 75
        assert event.is_negative_threshold is False

    def test_event_threshold_direction_negative(self):
        """Breakup should require affinity <= 25."""
        event = get_event_by_type("breakup")
        assert event.required_affinity == 25
        assert event.is_negative_threshold is True

    def test_event_special_requirements(self):
        """Marriage proposal should require dating status."""
        event = get_event_by_type("marriage_proposal")
        assert event.require_dating is True

    def test_event_childbirth_requirements(self):
        """Childbirth should require married status."""
        event = get_event_by_type("childbirth")
        assert event.require_married is True

    def test_event_elopement_requirements(self):
        """Elopement should require external obstacle."""
        event = get_event_by_type("elopement")
        assert event.require_external_obstacle is True

    def test_event_betrayal_negative(self):
        """Betrayal should be negative with low trust."""
        event = get_event_by_type("betrayal")
        assert event.category == EventCategory.NEGATIVE
        assert event.is_negative_threshold is True
        assert event.required_trust == 20

    def test_event_soulmate_min_interactions(self):
        """Soulmate should require minimum interactions."""
        event = get_event_by_type("soulmate")
        assert event.min_interaction_count == 10

    def test_event_business_partner_high_competence(self):
        """Business partner should require high competence."""
        event = get_event_by_type("business_partner")
        assert event.require_high_competence is True

    def test_event_sabotage_high_influence(self):
        """Sabotage should require high influence."""
        event = get_event_by_type("sabotage")
        assert event.require_high_influence is True

    def test_event_become_enemy_peak_affinity(self):
        """Become enemy should check peak affinity."""
        event = get_event_by_type("become_enemy")
        assert event.check_peak_affinity is True
        assert event.peak_affinity_threshold == 60

    def test_event_apprenticeship_high_respect(self):
        """Apprenticeship should require high respect."""
        event = get_event_by_type("apprenticeship")
        assert event.required_respect == 75

    def test_event_def_fields(self):
        """EventDef should store all configured fields."""
        event = RelationshipEventDef(
            event_type="test_event",
            category=EventCategory.SPECIAL,
            display_name="测试事件",
            required_affinity=50,
            era_variations={"modern": "测试"},
            description_template="{character} test",
        )
        assert event.event_type == "test_event"
        assert event.required_affinity == 50
        assert event.era_variations == {"modern": "测试"}
