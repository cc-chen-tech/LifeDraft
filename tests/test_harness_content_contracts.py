"""No-double public contracts for inventory and narrative content validators."""

from src.ai.harness.item_continuity_validator import ItemContinuityValidator
from src.ai.harness.narrative_validators import (
    validate_arc_hint_compliance,
    validate_conflict_directive_compliance,
    validate_three_act_structure,
    validate_world_event_integration,
)


class TestItemContinuityContracts:
    def test_unavailable_item_usage_is_rejected(self):
        context = {"player_state": {"items": {"长剑": {"status": "destroyed"}}}}

        passed, evidence, details = ItemContinuityValidator().validate(
            "李逍遥拔出长剑，剑锋映着月光。", context
        )

        assert passed is False
        assert "物品连续性违规" in evidence
        assert details["missing_items"] == ["长剑"]

    def test_owned_item_usage_is_accepted(self):
        context = {"player_state": {"items": {"灵药": {"status": "owned"}}}}

        passed, evidence, details = ItemContinuityValidator().validate(
            "李逍遥取出灵药，小心收好。", context
        )

        assert passed is True
        assert evidence == ""
        assert details["item_usages"][0]["item"] == "灵药"

    def test_item_acquired_before_use_is_exempt(self):
        context = {"player_state": {"items": {"宝剑": {"status": "lost"}}}}

        passed, evidence, details = ItemContinuityValidator().validate(
            "李逍遥获得宝剑后，立刻拔出宝剑应敌。", context
        )

        assert passed is True
        assert evidence == ""
        assert details["missing_items"] == []


class TestNarrativeHintContracts:
    def test_long_story_requires_multiple_three_act_signals(self):
        text = "平静的日子继续着。" * 70

        passed, _, details = validate_three_act_structure(text, {})

        assert passed is False
        assert details["phases_count"] == 0

    def test_arc_hint_requires_matching_stage_language(self):
        passed, evidence, details = validate_arc_hint_compliance(
            "一切如常，众人安静地度过了这一天。",
            {"narrative_hints": {"arc_hint": "角色正处于挣扎阶段"}},
        )

        assert passed is False
        assert "挣扎" in evidence
        assert details["matched_keywords"] == []

    def test_world_event_and_conflict_hints_are_independently_enforced(self):
        world_passed, _, world_details = validate_world_event_integration(
            "战争爆发后，城门外挤满了逃难的人。",
            {"narrative_hints": {"world_event_context": "战争爆发"}},
        )
        conflict_passed, conflict_evidence, conflict_details = validate_conflict_directive_compliance(
            "众人平静地散步，欣赏着傍晚的花园。",
            {"narrative_hints": {"conflict_directive": "增加人际对抗"}},
        )

        assert world_passed is True
        assert world_details["integrated"] is True
        assert conflict_passed is False
        assert "冲突指令" in conflict_evidence
        assert conflict_details["compliant"] is False
