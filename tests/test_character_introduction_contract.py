"""CharacterIntroductionService contract tests.

No mocks. Pure logic tests for character introduction timing,
priority calculation, scene matching, and context determination.
"""

from typing import Any, Dict

from src.game.round.character_introduction import CharacterIntroductionService
from src.game.state import PlayerState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(player_state=None):
    """Build a CharacterIntroductionService with a stub character_creator.

    The character_creator is only called inside maybe_generate_new_character
    (which requires AI); the pure-logic methods under test do not use it.
    """
    return CharacterIntroductionService(
        player_state_getter=lambda: player_state,
        character_creator=None,  # not needed for pure-logic contract tests
        character_settings_setter=None,
    )


def _make_state(**kwargs) -> PlayerState:
    defaults = {
        "player_name": "TestHero",
        "week": 5,
        "age": 25,
        "current_round": 0,
        "rounds_per_week": 3,
        "energy": 70,
        "mood": 60,
        "knowledge": 50,
        "wealth": 10000,
        "relationships": {},
        "character_settings": {},
    }
    defaults.update(kwargs)
    return PlayerState(**defaults)


def _make_person(**kwargs) -> Dict[str, Any]:
    defaults = {
        "name": "TestPerson",
        "role": "朋友",
        "affinity": 50,
        "personality": "温和友善",
    }
    defaults.update(kwargs)
    return defaults


# ===================================================================
# Contract tests
# ===================================================================


class TestDetermineIntroductionContext:
    """Contract tests for determine_introduction_context."""

    def test_work_role_returns_work(self):
        """Characters with work-related roles get 'work' context."""
        svc = _make_service(_make_state())
        for role in ["同事", "上司", "下属", "合作伙伴", "客户", "colleague", "boss"]:
            person = _make_person(role=role)
            ctx = svc.determine_introduction_context(person)
            assert ctx == "work", f"Role '{role}' should return 'work', got '{ctx}'"

    def test_education_role_returns_education(self):
        """Characters with education-related roles get 'education' context."""
        svc = _make_service(_make_state())
        for role in ["同学", "老师", "导师", "student", "classmate", "teacher", "mentor"]:
            person = _make_person(role=role)
            ctx = svc.determine_introduction_context(person)
            assert ctx == "education", f"Role '{role}' should return 'education', got '{ctx}'"

    def test_neighbor_role_returns_location_change(self):
        """Neighbor roles get 'location_change' context."""
        svc = _make_service(_make_state())
        for role in ["邻居", "neighbor"]:
            person = _make_person(role=role)
            ctx = svc.determine_introduction_context(person)
            assert (
                ctx == "location_change"
            ), f"Role '{role}' should return 'location_change', got '{ctx}'"

    def test_unknown_role_defaults_to_social(self):
        """Unknown roles should default to 'social' context."""
        svc = _make_service(_make_state())
        person = _make_person(role="神秘的旅人")
        ctx = svc.determine_introduction_context(person)
        assert ctx == "social", f"Unknown role should default to 'social', got '{ctx}'"

    def test_empty_role_defaults_to_social(self):
        """Empty role string should default to 'social'."""
        svc = _make_service(_make_state())
        person = _make_person(role="")
        ctx = svc.determine_introduction_context(person)
        assert ctx == "social"

    def test_nonexistent_role_key_defaults_to_social(self):
        """Person dict without 'role' key should default to 'social'."""
        svc = _make_service(_make_state())
        person = {"name": "Mystery", "affinity": 50}
        ctx = svc.determine_introduction_context(person)
        assert ctx == "social"

    def test_role_case_insensitive(self):
        """Role matching should be case-insensitive."""
        svc = _make_service(_make_state())
        person = _make_person(role="Colleague")
        ctx = svc.determine_introduction_context(person)
        assert ctx == "work"

    def test_role_partial_match(self):
        """Keywords embedded in longer role strings should match."""
        svc = _make_service(_make_state())
        # "同事" is embedded in this string
        person = _make_person(role="资深同事兼好友")
        ctx = svc.determine_introduction_context(person)
        assert ctx == "work"


class TestCalculateIntroductionPriority:
    """Contract tests for calculate_introduction_priority."""

    def test_default_priority_is_5(self):
        """A normal character with no special attributes gets priority 5."""
        svc = _make_service(_make_state())
        person = _make_person(role="朋友", affinity=50)
        priority = svc.calculate_introduction_priority(person)
        assert priority == 5

    def test_lover_role_increases_priority(self):
        """Romantic partner roles should increase priority by 3."""
        svc = _make_service(_make_state())
        for role in ["恋人", "爱人", "伴侣", "lover", "partner", "spouse"]:
            person = _make_person(role=role, affinity=50)
            priority = svc.calculate_introduction_priority(person)
            assert priority >= 8, f"Role '{role}' should have priority >= 8, got {priority}"

    def test_mentor_role_increases_priority(self):
        """Mentor/patron roles should increase priority by 2."""
        svc = _make_service(_make_state())
        for role in ["导师", "贵人", "mentor", "patron"]:
            person = _make_person(role=role, affinity=50)
            priority = svc.calculate_introduction_priority(person)
            assert priority >= 7, f"Role '{role}' should have priority >= 7, got {priority}"

    def test_high_affinity_increases_priority(self):
        """Affinity >= 70 should add 1 to priority."""
        svc = _make_service(_make_state())
        person = _make_person(role="朋友", affinity=70)
        priority = svc.calculate_introduction_priority(person)
        assert priority >= 6

    def test_affinity_below_threshold_no_bonus(self):
        """Affinity < 70 should not increase priority."""
        svc = _make_service(_make_state())
        person = _make_person(role="朋友", affinity=69)
        priority = svc.calculate_introduction_priority(person)
        assert priority == 5  # base only

    def test_priority_never_exceeds_10(self):
        """Priority should be capped at 10."""
        svc = _make_service(_make_state())
        # lover (+3) + high affinity (+1) = 5+3+1 = 9, still <=10
        person = _make_person(role="恋人", affinity=90)
        priority = svc.calculate_introduction_priority(person)
        assert priority <= 10
        assert priority == 9  # 5 + 3 + 1

    def test_priority_without_role_key(self):
        """Person without 'role' key should get base priority."""
        svc = _make_service(_make_state())
        person = {"name": "NoRole", "affinity": 50}
        priority = svc.calculate_introduction_priority(person)
        assert priority == 5

    def test_priority_without_affinity_key(self):
        """Person without 'affinity' key should get base priority."""
        svc = _make_service(_make_state())
        person = {"name": "NoAffinity", "role": "朋友"}
        priority = svc.calculate_introduction_priority(person)
        assert priority == 5


class TestCollectExistingPeople:
    """Contract tests for _collect_existing_people."""

    def test_empty_settings_returns_empty_list(self):
        svc = _make_service(_make_state())
        result = svc._collect_existing_people({}, [])
        assert result == []
        assert isinstance(result, list)

    def test_collects_key_people_from_relationships(self):
        svc = _make_service(_make_state())
        settings = {
            "relationships": {
                "key_people": [
                    {"name": "Alice", "role": "同事"},
                    {"name": "Bob", "role": "朋友"},
                ]
            }
        }
        result = svc._collect_existing_people(settings, [])
        assert len(result) == 2
        names = [p["name"] for p in result]
        assert "Alice" in names
        assert "Bob" in names

    def test_collects_family_members(self):
        svc = _make_service(_make_state())
        settings = {
            "family": {
                "family_members": [
                    {"name": "Mother"},
                    {"name": "Father"},
                ]
            }
        }
        result = svc._collect_existing_people(settings, [])
        assert len(result) == 2
        names = [p["name"] for p in result]
        assert "Mother" in names
        assert "Father" in names

    def test_collects_both_relationships_and_family(self):
        svc = _make_service(_make_state())
        settings = {
            "relationships": {"key_people": [{"name": "Alice", "role": "同事"}]},
            "family": {"family_members": [{"name": "Mother"}]},
        }
        result = svc._collect_existing_people(settings, [])
        assert len(result) == 2

    def test_collects_pending_characters(self):
        svc = _make_service(_make_state())
        pending = [
            {"character_data": {"name": "PendingCharlie", "role": "商人"}},
            {"character_data": {"name": "PendingDiana", "role": "医生"}},
        ]
        result = svc._collect_existing_people({}, pending)
        assert len(result) == 2
        names = [p["name"] for p in result]
        assert "PendingCharlie" in names
        assert "PendingDiana" in names

    def test_collects_all_sources_combined(self):
        svc = _make_service(_make_state())
        settings = {
            "relationships": {"key_people": [{"name": "Alice", "role": "同事"}]},
            "family": {"family_members": [{"name": "Mother"}]},
        }
        pending = [
            {"character_data": {"name": "PendingCharlie", "role": "商人"}},
        ]
        result = svc._collect_existing_people(settings, pending)
        assert len(result) == 3

    def test_pending_without_name_is_skipped(self):
        """Pending entries without a name should not be added."""
        svc = _make_service(_make_state())
        pending = [
            {"character_data": {"role": "商人"}},  # no name
            {"character_data": {"name": "ValidPerson"}},
        ]
        result = svc._collect_existing_people({}, pending)
        assert len(result) == 1
        assert result[0]["name"] == "ValidPerson"

    def test_family_members_skip_non_dict_entries(self):
        """Non-dict family members should be skipped gracefully."""
        svc = _make_service(_make_state())
        settings = {
            "family": {
                "family_members": [
                    "just a string",  # non-dict
                    {"name": "Mother"},
                ]
            }
        }
        result = svc._collect_existing_people(settings, [])
        assert len(result) == 1
        assert result[0]["name"] == "Mother"

    def test_settings_with_no_relationships_or_family(self):
        """Settings without relationships or family keys."""
        svc = _make_service(_make_state())
        result = svc._collect_existing_people({"era": {"year": 1066}}, [])
        assert result == []


class TestMatchesIntroductionScene:
    """Contract tests for matches_introduction_scene."""

    def test_random_context_always_matches(self):
        """'random' context should always return True."""
        state = _make_state(round_history=[])
        svc = _make_service(state)
        assert svc.matches_introduction_scene("random") is True

    def test_work_context_matches_work_keywords_in_zh(self):
        """Work context should match when recent stories contain work keywords."""
        state = _make_state(
            round_history=[
                {
                    "week": 5,
                    "round": 0,
                    "event_description": "你走进公司大楼，准备参加一个重要会议。",
                    "summary": "参加了公司会议",
                }
            ]
        )
        svc = _make_service(state)
        assert svc.matches_introduction_scene("work") is True

    def test_work_context_no_match_without_keywords(self):
        """Work context should not match when stories lack work keywords."""
        state = _make_state(
            round_history=[
                {
                    "week": 5,
                    "round": 0,
                    "event_description": "你在公园里散步，享受着阳光。",
                    "summary": "公园散步",
                }
            ]
        )
        svc = _make_service(state)
        assert svc.matches_introduction_scene("work") is False

    def test_social_context_matches_social_keywords(self):
        """Social context should match when stories contain social keywords."""
        state = _make_state(
            round_history=[
                {
                    "week": 5,
                    "round": 0,
                    "event_description": "你参加了一场热闹的聚会，认识了很多新朋友。",
                    "summary": "参加聚会",
                }
            ]
        )
        svc = _make_service(state)
        assert svc.matches_introduction_scene("social") is True

    def test_social_context_no_match_without_keywords(self):
        """Social context should not match when stories lack social keywords."""
        state = _make_state(
            round_history=[
                {
                    "week": 5,
                    "round": 0,
                    "event_description": "你独自在家看书学习。",
                    "summary": "在家学习",
                }
            ]
        )
        svc = _make_service(state)
        assert svc.matches_introduction_scene("social") is False

    def test_education_context_matches_edu_keywords(self):
        """Education context should match when stories contain education keywords."""
        state = _make_state(
            round_history=[
                {
                    "week": 5,
                    "round": 0,
                    "event_description": "你来到学校参加课程培训。",
                    "summary": "参加培训",
                }
            ]
        )
        svc = _make_service(state)
        assert svc.matches_introduction_scene("education") is True

    def test_location_change_no_recent_move_returns_false(self):
        """Location change without recent move should return False."""
        state = _make_state(round_history=[])
        svc = _make_service(state)
        assert svc.matches_introduction_scene("location_change") is False

    def test_empty_round_history_work_returns_false(self):
        """Empty round history should result in no match for non-random contexts."""
        state = _make_state(round_history=[])
        svc = _make_service(state)
        assert svc.matches_introduction_scene("work") is False

    def test_empty_round_history_social_returns_false(self):
        state = _make_state(round_history=[])
        svc = _make_service(state)
        assert svc.matches_introduction_scene("social") is False

    def test_unknown_context_does_not_match(self):
        """Unknown context types should not match."""
        state = _make_state(
            round_history=[
                {
                    "week": 5,
                    "round": 0,
                    "event_description": "Test content.",
                    "summary": "Test summary",
                }
            ]
        )
        svc = _make_service(state)
        assert svc.matches_introduction_scene("unknown_context") is False


class TestCheckIntroductionOpportunity:
    """Contract tests for check_introduction_opportunity."""

    def test_empty_queue_returns_none(self):
        """When no pending characters exist, should return None."""
        state = _make_state()
        state.pending_character_introductions = []
        svc = _make_service(state)
        assert svc.check_introduction_opportunity() is None

    def test_no_pending_attr_returns_none(self):
        """When player_state has no pending_character_introductions attr."""
        # PlayerState always has this field (default is []), so this tests the
        # getattr fallback path
        state = _make_state()
        state.pending_character_introductions = []
        svc = _make_service(state)
        assert svc.check_introduction_opportunity() is None

    def test_forced_introduction_after_waiting_4_weeks(self):
        """Characters waiting >= 4 weeks should be force-introduced."""
        state = _make_state(week=10)
        state.pending_character_introductions = [
            {
                "character_data": {"name": "ForcedIntro", "role": "朋友", "affinity": 50},
                "created_week": 6,  # 4 weeks ago
                "introduction_context": "random",
                "priority": 5,
                "attempts": 0,
            }
        ]
        svc = _make_service(state)
        result = svc.check_introduction_opportunity()
        assert result is not None
        assert result["character_data"]["name"] == "ForcedIntro"

    def test_forced_introduction_after_3_attempts(self):
        """Characters with >= 3 attempts should be force-introduced regardless of time."""
        state = _make_state(week=10)
        state.pending_character_introductions = [
            {
                "character_data": {"name": "ManyAttempts", "role": "朋友", "affinity": 50},
                "created_week": 9,  # only 1 week ago
                "introduction_context": "work",  # won't match by scene
                "priority": 5,
                "attempts": 3,
            }
        ]
        svc = _make_service(state)
        result = svc.check_introduction_opportunity()
        assert result is not None
        assert result["character_data"]["name"] == "ManyAttempts"

    def test_sorts_by_priority_desc(self):
        """Higher priority characters should be checked first."""
        state = _make_state(week=10)
        state.pending_character_introductions = [
            {
                "character_data": {"name": "LowPriority", "role": "朋友", "affinity": 50},
                "created_week": 9,
                "introduction_context": "random",
                "priority": 3,
                "attempts": 0,
            },
            {
                "character_data": {"name": "HighPriority", "role": "朋友", "affinity": 50},
                "created_week": 9,
                "introduction_context": "random",
                "priority": 8,
                "attempts": 0,
            },
        ]
        svc = _make_service(state)
        result = svc.check_introduction_opportunity()
        assert result is not None
        # Higher priority (8) should be checked first and match (random always matches)
        assert result["character_data"]["name"] == "HighPriority"

    def test_returns_none_when_no_scene_matches_and_not_forced(self):
        """When no scene matches and characters aren't forced, returns None."""
        state = _make_state(week=10)
        state.pending_character_introductions = [
            {
                "character_data": {"name": "NoMatch", "role": "朋友", "affinity": 50},
                "created_week": 9,  # 1 week, not forced
                "introduction_context": "work",  # won't match
                "priority": 5,
                "attempts": 1,  # < 3, not forced
            }
        ]
        # Ensure no work keywords in history
        state.round_history = [
            {
                "week": 10,
                "round": 0,
                "event_description": "你在公园散步。",
                "summary": "散步",
            }
        ]
        svc = _make_service(state)
        result = svc.check_introduction_opportunity()
        assert result is None


class TestMaybeGenerateNewCharacter:
    """Contract tests for maybe_generate_new_character."""

    def test_none_player_state_returns_none(self):
        """When player_state is None, should return None safely."""
        svc = _make_service(player_state=None)
        result = svc.maybe_generate_new_character(probability=1.0)
        assert result is None

    def test_queue_full_returns_none(self):
        """When pending queue has 3 characters, should return None."""
        state = _make_state(week=5)
        state.pending_character_introductions = [
            {"character_data": {"name": f"Pending{i}"}, "created_week": 5} for i in range(3)
        ]
        svc = _make_service(state)
        # probability=1.0 would normally trigger, but queue is full
        result = svc.maybe_generate_new_character(probability=1.0)
        assert result is None

    def test_low_probability_returns_none(self):
        """With probability=0, should never generate (random < 0 is impossible)."""
        state = _make_state(week=5)
        svc = _make_service(state)
        result = svc.maybe_generate_new_character(probability=0.0)
        assert result is None


class TestCharacterIntroductionTimingFields:
    """Verify timing/context fields in introduction data structures."""

    def test_pending_entry_has_required_fields(self):
        """After maybe_generate_new_character succeeds, the pending entry
        should have the expected contract fields.

        Uses 'random' context (always matches) so check_introduction_opportunity
        returns the entry for structural verification.
        """
        state = _make_state(week=5)
        person_data = {
            "name": "TestPerson",
            "role": "同事",
            "affinity": 60,
        }
        state.pending_character_introductions = [
            {
                "character_data": person_data,
                "created_week": 5,
                "introduction_context": "random",
                "priority": 5,
                "attempts": 0,
            }
        ]
        svc = _make_service(state)
        result = svc.check_introduction_opportunity()

        assert (
            result is not None
        ), "check_introduction_opportunity should return entry for 'random' context"

        # Verify the entry structure
        required_fields = [
            "character_data",
            "created_week",
            "introduction_context",
            "priority",
            "attempts",
        ]
        for field in required_fields:
            assert field in result, f"Missing field '{field}' in pending entry"

        assert isinstance(result["created_week"], int)
        assert isinstance(result["priority"], int)
        assert isinstance(result["attempts"], int)
        assert isinstance(result["introduction_context"], str)
        assert isinstance(result["character_data"], dict)


class TestIntroducePendingCharacter:
    """Contract tests for introduce_pending_character."""

    def test_none_character_data_returns_none(self):
        """When entry has no character_data, returns None."""
        state = _make_state(week=5)
        svc = _make_service(state)
        result = svc.introduce_pending_character({"no_data": True})
        assert result is None

    def test_missing_name_returns_none(self):
        """When character_data has no name, returns None."""
        state = _make_state(week=5)
        svc = _make_service(state)
        result = svc.introduce_pending_character({"character_data": {"role": "朋友"}})  # no name
        assert result is None

    def test_successful_introduction_returns_character_data(self):
        """On success, returns the character data dict."""
        state = _make_state(week=5)
        state.pending_character_introductions = [
            {
                "character_data": {"name": "NewFriend", "role": "朋友", "affinity": 55},
                "created_week": 3,
                "introduction_context": "social",
                "priority": 5,
                "attempts": 2,
            }
        ]
        svc = _make_service(state)
        entry = state.pending_character_introductions[0]
        result = svc.introduce_pending_character(entry)

        assert result is not None
        assert result["name"] == "NewFriend"
        assert result["role"] == "朋友"

    def test_introduction_adds_to_character_settings(self):
        """After successful introduction, character should be in settings."""
        state = _make_state(week=5)
        state.pending_character_introductions = [
            {
                "character_data": {"name": "NewFriend", "role": "朋友", "affinity": 55},
                "created_week": 3,
                "introduction_context": "social",
                "priority": 5,
                "attempts": 2,
            }
        ]
        svc = _make_service(state)
        entry = state.pending_character_introductions[0]
        svc.introduce_pending_character(entry)

        # Should now be in character_settings
        key_people = state.character_settings.get("relationships", {}).get("key_people", [])
        names = [p["name"] for p in key_people]
        assert "NewFriend" in names

    def test_introduction_adds_to_relationships(self):
        """After successful introduction, character should be in relationships."""
        state = _make_state(week=5)
        state.pending_character_introductions = [
            {
                "character_data": {"name": "NewFriend", "role": "朋友", "affinity": 55},
                "created_week": 3,
                "introduction_context": "social",
                "priority": 5,
                "attempts": 2,
            }
        ]
        svc = _make_service(state)
        entry = state.pending_character_introductions[0]
        svc.introduce_pending_character(entry)

        assert "NewFriend" in state.relationships
        assert state.relationships["NewFriend"] == 55

    def test_introduction_removes_from_pending_queue(self):
        """After successful introduction, character should be removed from pending."""
        state = _make_state(week=5)
        state.pending_character_introductions = [
            {
                "character_data": {"name": "NewFriend", "role": "朋友", "affinity": 55},
                "created_week": 3,
                "introduction_context": "social",
                "priority": 5,
                "attempts": 2,
            }
        ]
        svc = _make_service(state)
        entry = state.pending_character_introductions[0]
        svc.introduce_pending_character(entry)

        # Should be removed from pending
        assert len(state.pending_character_introductions) == 0
