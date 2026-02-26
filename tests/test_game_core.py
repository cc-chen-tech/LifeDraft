"""Tests for game core logic: decisions, narrative_manager, world_model, world_model_updater."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.game.state import PlayerState, CharacterState
from src.game.decisions import (
    calculate_character_effects,
    apply_character_effects,
    get_character_interaction_context,
    process_decision,
    _generate_fallback_result,
)
from src.game.narrative_manager import NarrativeManager
from src.game.world_model import (
    WorldModel, LocationInfo, CareerInfo, Commitment,
    CausalChain, PhysicalState, CharacterProfile,
    CAREER_LEVELS, CAREER_LEVEL_INDEX, MAX_CAREER_JUMP,
)
from src.game.world_model_updater import WorldModelUpdater


# ==================== Decisions Tests ====================

class TestCalculateCharacterEffects:
    """Test calculate_character_effects function."""

    def test_positive_relationship_change(self):
        """Test positive relationship change derives trust/respect/mood."""
        effects = {"relationships": {"Friend": 10}}
        player = PlayerState()
        result = calculate_character_effects(effects, player)
        assert "Friend" in result
        assert result["Friend"]["affinity"] == 10
        assert result["Friend"]["trust"] > 0
        assert result["Friend"]["respect"] > 0
        assert result["Friend"]["mood"] > 0

    def test_negative_relationship_change(self):
        """Test negative relationship change derives negative trust/respect/mood."""
        effects = {"relationships": {"Enemy": -10}}
        player = PlayerState()
        result = calculate_character_effects(effects, player)
        assert result["Enemy"]["affinity"] == -10
        assert result["Enemy"]["trust"] < 0
        assert result["Enemy"]["respect"] < 0
        assert result["Enemy"]["mood"] < 0

    def test_detailed_character_effects_override(self):
        """Test that character_effects override relationship-derived values."""
        effects = {
            "relationships": {"Friend": 10},
            "character_effects": {"Friend": {"trust": 20}}
        }
        player = PlayerState()
        result = calculate_character_effects(effects, player)
        assert result["Friend"]["trust"] == 20  # Overridden
        assert result["Friend"]["affinity"] == 10  # From relationships

    def test_empty_effects(self):
        """Test empty effects returns empty dict."""
        result = calculate_character_effects({}, PlayerState())
        assert result == {}

    def test_zero_change(self):
        """Test zero relationship change does not create entries."""
        effects = {"relationships": {}}
        result = calculate_character_effects(effects, PlayerState())
        assert result == {}


class TestApplyCharacterEffects:
    """Test apply_character_effects function."""

    def test_apply_effects_to_existing_character(self):
        """Test applying effects to an existing character."""
        player = PlayerState()
        char = CharacterState(name="Friend", affinity=50, trust=50)
        player.characters["Friend"] = char.model_dump()
        player.relationships["Friend"] = 50

        effects = {"Friend": {"affinity": 10, "trust": 5}}
        triggered = apply_character_effects(player, effects)
        assert isinstance(triggered, list)

    def test_apply_effects_nonexistent_character(self):
        """Test applying effects to nonexistent character."""
        player = PlayerState()
        effects = {"NonExistent": {"affinity": 10}}
        triggered = apply_character_effects(player, effects)
        assert triggered == []


class TestGetCharacterInteractionContext:
    """Test get_character_interaction_context function."""

    def test_with_characters(self):
        """Test context string with characters."""
        player = PlayerState()
        char = CharacterState(name="Friend", role="roommate", affinity=70)
        player.characters["Friend"] = char.model_dump()

        context = get_character_interaction_context(player, ["Friend"])
        assert "Friend" in context
        assert "互动涉及" in context

    def test_with_no_names(self):
        """Test empty names list returns empty string."""
        context = get_character_interaction_context(PlayerState(), [])
        assert context == ""

    def test_with_nonexistent_character(self):
        """Test nonexistent character returns empty string."""
        context = get_character_interaction_context(PlayerState(), ["Nobody"])
        assert context == ""


class TestProcessDecision:
    """Test process_decision function."""

    def test_valid_decision(self):
        """Test processing a valid decision."""
        player = PlayerState(energy=70, mood=60)
        options = [
            {"text": "Option A", "effects": {"energy": -10, "mood": 5}},
            {"text": "Option B", "effects": {"energy": 10, "mood": -5}},
        ]
        result = process_decision(
            player, "Test event", 0, options,
            language="zh", generate_result_text=False
        )
        assert result["success"] is True
        assert player.energy == 60  # 70 - 10
        assert player.mood == 65   # 60 + 5
        assert len(player.decision_history) == 1

    def test_invalid_option_index(self):
        """Test invalid option index raises ValueError."""
        player = PlayerState()
        options = [{"text": "Only option", "effects": {}}]
        with pytest.raises(ValueError):
            process_decision(player, "Test", 5, options, generate_result_text=False)

    def test_negative_option_index(self):
        """Test negative option index raises ValueError."""
        player = PlayerState()
        options = [{"text": "Option", "effects": {}}]
        with pytest.raises(ValueError):
            process_decision(player, "Test", -1, options, generate_result_text=False)

    def test_with_relationship_effects(self):
        """Test decision with relationship effects."""
        player = PlayerState()
        player.relationships["Friend"] = 50
        char = CharacterState(name="Friend", affinity=50)
        player.characters["Friend"] = char.model_dump()

        options = [
            {"text": "Help friend", "effects": {"relationships": {"Friend": 10}}}
        ]
        result = process_decision(
            player, "Friend needs help", 0, options,
            generate_result_text=False
        )
        assert result["success"] is True
        assert player.relationships["Friend"] > 50

    def test_with_ai_result_generation(self):
        """Test decision with AI-generated result text."""
        player = PlayerState()
        mock_gen = Mock()
        mock_gen.generate_completion.return_value = "You feel great!"

        options = [{"text": "Do it", "effects": {"mood": 5}}]
        result = process_decision(
            player, "Event", 0, options,
            generate_result_text=True, ai_generator=mock_gen
        )
        assert result["result_text"] == "You feel great!"


class TestGenerateFallbackResult:
    """Test _generate_fallback_result function."""

    def test_zh_with_all_effects(self):
        """Test Chinese fallback with all effect types."""
        effects = {"energy": -10, "mood": 5, "knowledge": 3, "wealth": 1000}
        result = _generate_fallback_result(effects, "zh")
        assert "精力" in result
        assert "情绪" in result
        assert "学识" in result
        assert "财富" in result

    def test_en_with_effects(self):
        """Test English fallback."""
        effects = {"energy": 10}
        result = _generate_fallback_result(effects, "en")
        assert "Energy" in result

    def test_empty_effects(self):
        """Test empty effects."""
        result = _generate_fallback_result({}, "zh")
        assert "后果" in result


# ==================== NarrativeManager Tests ====================

class TestNarrativeManagerStorylines:
    """Test NarrativeManager storyline processing."""

    def test_new_storyline(self):
        """Test adding a new storyline."""
        player = PlayerState(week=5)
        updates = [{"action": "new", "description": "A mysterious letter arrives"}]
        NarrativeManager.process_storyline_updates(player, updates)
        assert len(player.pending_storylines) == 1
        assert player.pending_storylines[0]["description"] == "A mysterious letter arrives"
        assert player.pending_storylines[0]["created_week"] == 5

    def test_resolve_storyline(self):
        """Test resolving an existing storyline."""
        player = PlayerState(week=10)
        player.pending_storylines = [
            {"description": "A mysterious letter", "created_week": 5,
             "importance": "medium", "status": "active",
             "related_characters": [], "last_mentioned_week": 5}
        ]
        updates = [{"action": "resolved", "description": "A mysterious letter"}]
        NarrativeManager.process_storyline_updates(player, updates)
        assert len(player.pending_storylines) == 0

    def test_continue_storyline(self):
        """Test continuing (mentioning) a storyline."""
        player = PlayerState(week=10)
        player.pending_storylines = [
            {"description": "ongoing project", "created_week": 5,
             "importance": "medium", "status": "active",
             "related_characters": [], "last_mentioned_week": 5}
        ]
        updates = [{"action": "continues", "description": "ongoing project"}]
        NarrativeManager.process_storyline_updates(player, updates)
        assert player.pending_storylines[0]["last_mentioned_week"] == 10

    def test_stale_storyline_cleanup(self):
        """Test stale storylines are cleaned up."""
        player = PlayerState(week=30)
        player.pending_storylines = [
            {"description": "old story", "created_week": 1,
             "importance": "medium", "status": "active",
             "related_characters": [], "last_mentioned_week": 1}  # 29 weeks stale
        ]
        # Must pass non-empty list; empty list triggers early return before cleanup
        NarrativeManager.process_storyline_updates(
            player, [{"action": "resolved", "description": "nonexistent_xyz"}])
        assert len(player.pending_storylines) == 0

    def test_high_importance_demoted_to_medium(self):
        """Test high importance storyline demoted after 8 weeks."""
        player = PlayerState(week=15)
        player.pending_storylines = [
            {"description": "critical plot", "created_week": 1,
             "importance": "high", "status": "active",
             "related_characters": [], "last_mentioned_week": 5}  # 10 weeks since mention
        ]
        # Must pass non-empty list; empty list triggers early return before cleanup
        NarrativeManager.process_storyline_updates(
            player, [{"action": "resolved", "description": "nonexistent_xyz"}])
        assert player.pending_storylines[0]["importance"] == "medium"

    def test_none_player_state(self):
        """Test with None player state does not crash."""
        NarrativeManager.process_storyline_updates(None, [{"action": "new", "description": "test"}])

    def test_empty_updates(self):
        """Test with empty updates list."""
        player = PlayerState()
        NarrativeManager.process_storyline_updates(player, [])


class TestNarrativeManagerFacts:
    """Test NarrativeManager fact processing."""

    def test_new_fact(self):
        """Test adding a new fact."""
        player = PlayerState(week=5)
        updates = [{"action": "new", "subject": "player", "category": "career",
                    "fact": "Started new job at tech company"}]
        NarrativeManager.process_fact_updates(player, updates)
        assert len(player.established_facts) == 1
        assert player.established_facts[0]["subject"] == "player"

    def test_update_fact(self):
        """Test updating an existing fact."""
        player = PlayerState(week=10)
        player.established_facts = [
            {"subject": "player", "category": "career",
             "fact": "Works at company A", "established_week": 5}
        ]
        updates = [{"action": "update", "subject": "player",
                    "fact": "Promoted to manager at company A"}]
        NarrativeManager.process_fact_updates(player, updates)
        assert player.established_facts[0]["fact"] == "Promoted to manager at company A"

    def test_remove_fact(self):
        """Test removing a fact."""
        player = PlayerState(week=10)
        player.established_facts = [
            {"subject": "old_topic", "category": "situation",
             "fact": "No longer relevant", "established_week": 1}
        ]
        updates = [{"action": "remove", "subject": "old_topic"}]
        NarrativeManager.process_fact_updates(player, updates)
        assert len(player.established_facts) == 0

    def test_fact_limit_50(self):
        """Test facts are limited to 50."""
        player = PlayerState(week=5)
        player.established_facts = [
            {"subject": f"subject_{i}", "fact": f"fact_{i}",
             "category": "situation", "established_week": i}
            for i in range(55)
        ]
        # Must pass non-empty list; empty list triggers early return before limit check
        NarrativeManager.process_fact_updates(
            player, [{"action": "remove", "subject": "nonexistent_xyz"}])
        assert len(player.established_facts) <= 50

    def test_update_nonexistent_fact_creates_new(self):
        """Test updating nonexistent fact creates a new one."""
        player = PlayerState(week=5)
        updates = [{"action": "update", "subject": "new_subject",
                    "fact": "New fact"}]
        NarrativeManager.process_fact_updates(player, updates)
        assert len(player.established_facts) == 1


class TestNarrativeManagerForeshadowing:
    """Test NarrativeManager foreshadowing seed processing."""

    def test_process_new_seeds(self):
        """Test adding new foreshadowing seeds."""
        player = PlayerState(week=5)
        new_seeds = [{"description": "A strange noise in the attic",
                      "seed_type": "mystery",
                      "related_characters": ["Friend"]}]
        NarrativeManager.process_foreshadowing_seeds(player, new_seeds)
        assert len(player.foreshadowing_seeds) == 1
        assert player.foreshadowing_seeds[0]["seed_type"] == "mystery"
        assert player.foreshadowing_seeds[0]["planted_week"] == 5

    def test_duplicate_seed_not_added(self):
        """Test duplicate seeds are skipped."""
        player = PlayerState(week=5)
        player.foreshadowing_seeds = [
            {"description": "A strange noise", "planted_week": 3, "activated": False}
        ]
        new_seeds = [{"description": "A strange noise in the attic"}]  # Substring match
        NarrativeManager.process_foreshadowing_seeds(player, new_seeds)
        assert len(player.foreshadowing_seeds) == 1  # Not added

    def test_expired_seeds_cleaned(self):
        """Test expired seeds are cleaned up."""
        player = PlayerState(week=70)
        player.foreshadowing_seeds = [
            {"description": "old seed", "planted_week": 1, "activated": False,
             "seed_type": "mystery", "narrative_weight": "supporting"}
        ]
        NarrativeManager.process_foreshadowing_seeds(player, [])
        assert len(player.foreshadowing_seeds) == 0

    def test_activated_seeds_cleaned_after_4_weeks(self):
        """Test activated seeds cleaned up 4 weeks after activation."""
        player = PlayerState(week=20)
        player.foreshadowing_seeds = [
            {"description": "activated seed", "planted_week": 5,
             "activated": True, "activation_week": 14}  # 6 weeks ago
        ]
        NarrativeManager.process_foreshadowing_seeds(player, [])
        assert len(player.foreshadowing_seeds) == 0

    def test_select_foreshadowing_seed_empty(self):
        """Test selecting from empty seeds returns None."""
        player = PlayerState(week=10)
        result = NarrativeManager.select_foreshadowing_seed(player)
        assert result is None

    def test_seed_limit_20(self):
        """Test active seeds limited to 20."""
        player = PlayerState(week=5)
        # Add 25 seeds
        for i in range(25):
            player.foreshadowing_seeds.append({
                "description": f"seed_{i}",
                "planted_week": 5,
                "activated": False,
                "seed_type": "mystery",
                "narrative_weight": "supporting",
                "maturity_weeks": 8,
                "obfuscation_level": 0.5,
                "recycle_method": "echo",
                "related_characters": [],
                "related_storylines": [],
                "original_context": "",
                "activation_week": None,
            })
        NarrativeManager.process_foreshadowing_seeds(player, [])
        active = [s for s in player.foreshadowing_seeds if not s.get("activated", False)]
        assert len(active) <= 20


class TestNarrativeManagerHabits:
    """Test NarrativeManager habit processing."""

    def test_new_habit(self):
        """Test adding a new habit."""
        player = PlayerState(week=5)
        updates = [{"action": "new", "character": "Friend",
                    "habit": "Always arrives late", "category": "behavioral"}]
        NarrativeManager.process_habit_updates(player, updates)
        assert len(player.character_habits) == 1
        assert player.character_habits[0]["habit"] == "Always arrives late"

    def test_strengthen_habit(self):
        """Test strengthening an existing habit."""
        player = PlayerState(week=10)
        player.character_habits = [
            {"character": "Friend", "habit": "arrives late",
             "strength": "emerging", "last_seen_week": 5, "category": "behavioral"}
        ]
        updates = [{"action": "strengthen", "character": "Friend",
                    "habit": "arrives late"}]
        NarrativeManager.process_habit_updates(player, updates)
        assert player.character_habits[0]["strength"] == "moderate"

    def test_weaken_habit(self):
        """Test weakening a habit."""
        player = PlayerState(week=10)
        player.character_habits = [
            {"character": "Friend", "habit": "arrives late",
             "strength": "moderate", "last_seen_week": 5, "category": "behavioral"}
        ]
        updates = [{"action": "weaken", "character": "Friend",
                    "habit": "arrives late"}]
        NarrativeManager.process_habit_updates(player, updates)
        assert player.character_habits[0]["strength"] == "emerging"

    def test_weaken_emerging_removes(self):
        """Test weakening an emerging habit removes it."""
        player = PlayerState(week=10)
        player.character_habits = [
            {"character": "Friend", "habit": "arrives late",
             "strength": "emerging", "last_seen_week": 5, "category": "behavioral"}
        ]
        updates = [{"action": "weaken", "character": "Friend",
                    "habit": "arrives late"}]
        NarrativeManager.process_habit_updates(player, updates)
        assert len(player.character_habits) == 0

    def test_remove_habit(self):
        """Test removing a habit."""
        player = PlayerState(week=10)
        player.character_habits = [
            {"character": "Friend", "habit": "arrives late",
             "strength": "moderate", "last_seen_week": 5, "category": "behavioral"}
        ]
        updates = [{"action": "remove", "character": "Friend",
                    "habit": "arrives late", "reason": "changed behavior"}]
        NarrativeManager.process_habit_updates(player, updates)
        assert len(player.character_habits) == 0

    def test_change_habit(self):
        """Test changing a habit to a new one."""
        player = PlayerState(week=10)
        player.character_habits = [
            {"character": "Friend", "habit": "arrives late",
             "strength": "moderate", "last_seen_week": 5, "category": "behavioral"}
        ]
        updates = [{"action": "change", "character": "Friend",
                    "old_habit": "arrives late",
                    "new_habit": "arrives on time"}]
        NarrativeManager.process_habit_updates(player, updates)
        assert player.character_habits[0]["habit"] == "arrives on time"

    def test_habit_limit_per_character(self):
        """Test habits limited to 10 per character."""
        player = PlayerState(week=5)
        for i in range(15):
            player.character_habits.append({
                "character": "Friend",
                "habit": f"habit_{i}",
                "strength": "moderate",
                "last_seen_week": 5,
                "category": "behavioral"
            })
        # Must pass non-empty list; empty list triggers early return before limit check
        NarrativeManager.process_habit_updates(
            player, [{"action": "remove", "character": "Nobody", "habit": "nothing"}])
        friend_habits = [h for h in player.character_habits if h["character"] == "Friend"]
        assert len(friend_habits) <= 10


# ==================== WorldModel Tests ====================

class TestWorldModelDataClasses:
    """Test WorldModel data classes."""

    def test_location_info_serialization(self):
        """Test LocationInfo to_dict and from_dict."""
        loc = LocationInfo(location="北京市朝阳区", region="北京",
                          since_week=5, travel_mode="resident")
        d = loc.to_dict()
        restored = LocationInfo.from_dict(d)
        assert restored.location == "北京市朝阳区"
        assert restored.region == "北京"

    def test_career_info_serialization(self):
        """Test CareerInfo serialization."""
        career = CareerInfo(current_job="产品经理", employer="Tech Co",
                           level="senior", since_week=10)
        d = career.to_dict()
        restored = CareerInfo.from_dict(d)
        assert restored.current_job == "产品经理"
        assert restored.level == "senior"

    def test_commitment_serialization(self):
        """Test Commitment serialization."""
        commit = Commitment(description="完成项目", parties=["Boss"],
                           deadline_week=20, status="pending")
        d = commit.to_dict()
        restored = Commitment.from_dict(d)
        assert restored.description == "完成项目"
        assert restored.deadline_week == 20

    def test_causal_chain_serialization(self):
        """Test CausalChain serialization."""
        chain = CausalChain(cause="得罪了领导", expected_consequence="影响晋升",
                           characters=["Boss"], created_week=5)
        d = chain.to_dict()
        restored = CausalChain.from_dict(d)
        assert restored.cause == "得罪了领导"
        assert restored.resolved is False

    def test_physical_state_serialization(self):
        """Test PhysicalState serialization."""
        state = PhysicalState(condition="右腿骨折", severity="severe",
                             since_week=3, expected_recovery_week=15)
        d = state.to_dict()
        restored = PhysicalState.from_dict(d)
        assert restored.condition == "右腿骨折"
        assert restored.expected_recovery_week == 15

    def test_character_profile_serialization(self):
        """Test CharacterProfile serialization."""
        profile = CharacterProfile(
            character="Friend",
            behavioral_traits=["冲突回避型"],
            speech_style="说话直接",
            evidence_count=3,
            last_updated_week=10
        )
        d = profile.to_dict()
        restored = CharacterProfile.from_dict(d)
        assert restored.character == "Friend"
        assert restored.evidence_count == 3


class TestWorldModel:
    """Test WorldModel class."""

    def test_create_empty_world_model(self):
        """Test creating an empty WorldModel."""
        wm = WorldModel()
        assert wm.current_week == 0
        assert len(wm.character_locations) == 0
        assert len(wm.career_records) == 0

    def test_from_player_state_empty(self):
        """Test building WorldModel from empty PlayerState."""
        player = PlayerState()
        wm = WorldModel.from_player_state(player)
        assert wm.current_week == 0

    def test_from_player_state_with_locations(self):
        """Test building WorldModel with location data."""
        player = PlayerState(week=10)
        player.world_model_data = {
            "character_locations": {
                "player": {"location": "北京", "region": "北京",
                          "since_week": 0, "travel_mode": "resident"}
            }
        }
        wm = WorldModel.from_player_state(player)
        assert "player" in wm.character_locations
        assert wm.character_locations["player"].location == "北京"

    def test_career_levels_ordered(self):
        """Test career levels are properly ordered."""
        assert CAREER_LEVELS.index("intern") < CAREER_LEVELS.index("junior")
        assert CAREER_LEVELS.index("junior") < CAREER_LEVELS.index("senior")
        assert CAREER_LEVELS.index("senior") < CAREER_LEVELS.index("executive")


# ==================== WorldModelUpdater Tests ====================

class TestWorldModelUpdaterLocations:
    """Test WorldModelUpdater location processing."""

    def test_move_location(self):
        """Test processing a move update."""
        player = PlayerState(week=5)
        player.world_model_data = {"character_locations": {}}
        updates = [{"action": "move", "character": "player",
                    "to": "上海市浦东区", "mode": "resident"}]
        WorldModelUpdater.process_location_updates(player, updates)
        locs = player.world_model_data["character_locations"]
        assert "player" in locs
        assert locs["player"]["location"] == "上海市浦东区"

    def test_confirm_location(self):
        """Test confirming a location."""
        player = PlayerState(week=5)
        player.world_model_data = {"character_locations": {}}
        updates = [{"action": "confirm", "character": "player",
                    "location": "北京市朝阳区"}]
        WorldModelUpdater.process_location_updates(player, updates)
        locs = player.world_model_data["character_locations"]
        assert "player" in locs

    def test_none_player(self):
        """Test with None player does not crash."""
        WorldModelUpdater.process_location_updates(None, [{"action": "move"}])

    def test_empty_updates(self):
        """Test with empty updates."""
        player = PlayerState()
        player.world_model_data = {"character_locations": {}}
        WorldModelUpdater.process_location_updates(player, [])


class TestWorldModelUpdaterCareers:
    """Test WorldModelUpdater career processing."""

    def test_process_career_updates(self):
        """Test processing career updates."""
        player = PlayerState(week=10)
        player.world_model_data = {"career_records": {}}
        updates = [{"action": "new_job", "character": "player",
                    "new_role": "产品经理", "employer": "Tech Co",
                    "level": "mid"}]
        WorldModelUpdater.process_career_updates(player, updates)
        careers = player.world_model_data["career_records"]
        assert "player" in careers
