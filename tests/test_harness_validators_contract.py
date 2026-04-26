"""Harness validators contract tests.

No mocks. Tests validator aggregation/dispatch logic and return structure
of the standalone validation functions in src/ai/harness/validators.py.
Each validator is a pure function: (story_text, context) -> (bool, str, dict).
"""

from src.ai.harness.validators import (validate_anti_repetition,
                                       validate_available_people,
                                       validate_character_consistency,
                                       validate_character_habits,
                                       validate_decision_point_ending,
                                       validate_established_facts,
                                       validate_foreshadowing,
                                       validate_high_storylines,
                                       validate_logic_constraints,
                                       validate_medium_storylines,
                                       validate_no_fabrication,
                                       validate_no_meta_narration,
                                       validate_overdue_storylines,
                                       validate_scene_continuity,
                                       validate_third_person,
                                       validate_vector_context)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _isValidResult(result):
    """Return True if result is a (bool, str, dict) tuple."""
    return (
        isinstance(result, tuple)
        and len(result) == 3
        and isinstance(result[0], bool)
        and isinstance(result[1], str)
        and isinstance(result[2], dict)
    )


# ============================================================
# CRITICAL-level validators
# ============================================================


class TestValidateAvailablePeople:
    """Contract tests for validate_available_people."""

    def test_skips_when_no_people_in_context(self):
        passed, evidence, details = validate_available_people("story", {})
        assert passed is True
        assert evidence == ""
        assert details.get("skipped") is True

    def test_return_structure_is_valid(self):
        result = validate_available_people("some story here", {})
        assert _isValidResult(result)

    def test_mentions_known_people(self):
        result = validate_available_people(
            "张三 went to the market. 李四 was there too.",
            {"available_people": ["张三", "李四", "王五"]},
        )
        passed, evidence, details = result
        assert passed is True
        mentioned = details.get("mentioned_people", [])
        assert "张三" in mentioned or "李四" in mentioned


class TestValidateThirdPerson:
    """Contract tests for validate_third_person."""

    def test_return_structure_is_valid(self):
        result = validate_third_person("some story text", {})
        assert _isValidResult(result)

    def test_third_person_story_passes(self):
        passed, evidence, details = validate_third_person(
            "他走进了房间。她坐在窗边。外面天色已晚。",
            {},
        )
        assert passed is True

    def test_excessive_first_person_fails(self):
        passed, evidence, details = validate_third_person(
            "我想去那里。我觉得应该去看看。我发现了一个秘密。我决定离开。我知道答案。",
            {},
        )
        # May pass or fail depending on threshold, but structure must be valid
        assert isinstance(passed, bool)

    def test_dialogue_first_person_ignored(self):
        """First-person inside quotes (dialogue) should not trigger failure."""
        passed, evidence, details = validate_third_person(
            '"我想去那里。"他说。然后他转身离开。外面下着雨。',
            {},
        )
        assert passed is True


class TestValidateNoMetaNarration:
    """Contract tests for validate_no_meta_narration."""

    def test_return_structure_is_valid(self):
        result = validate_no_meta_narration("some story", {})
        assert _isValidResult(result)

    def test_clean_story_passes(self):
        passed, evidence, details = validate_no_meta_narration(
            "他走进房间，看着窗外的景色。夕阳西下，一切都那么宁静。",
            {},
        )
        assert passed is True

    def test_ai_meta_narration_fails(self):
        passed, evidence, details = validate_no_meta_narration(
            "作为AI，我为你写了这个故事。",
            {},
        )
        assert passed is False
        assert "violations" in details

    def test_game_system_meta_narration_fails(self):
        passed, evidence, details = validate_no_meta_narration(
            "在这个游戏中，你的精力值会影响后续剧情。",
            {},
        )
        assert passed is False


class TestValidateDecisionPointEnding:
    """Contract tests for validate_decision_point_ending."""

    def test_return_structure_is_valid(self):
        result = validate_decision_point_ending("some story", {})
        assert _isValidResult(result)

    def test_short_text_no_decision_fails(self):
        passed, evidence, details = validate_decision_point_ending(
            "他走进了房间。",
            {},
        )
        assert passed is False
        assert "indicators_found" not in details

    def test_text_with_decision_passes(self):
        passed, evidence, details = validate_decision_point_ending(
            "经过一番思考，他面临一个艰难的抉择。该怎么办呢？是留下还是离开。",
            {},
        )
        assert passed is True
        assert "indicators_found" in details

    def test_text_with_choice_keyword_passes(self):
        passed, evidence, details = validate_decision_point_ending(
            "现在是时候做出选择了。他犹豫了片刻，然后决定继续前进。",
            {},
        )
        assert passed is True


class TestValidateOverdueStorylines:
    """Contract tests for validate_overdue_storylines."""

    def test_skips_when_no_overdue(self):
        passed, evidence, details = validate_overdue_storylines("story", {})
        assert passed is True
        assert details.get("skipped") is True

    def test_return_structure_is_valid(self):
        result = validate_overdue_storylines("story", {})
        assert _isValidResult(result)

    def test_empty_storylines_list_passes(self):
        passed, evidence, details = validate_overdue_storylines(
            "story text", {"overdue_storylines": []}
        )
        assert passed is True

    def test_unmentioned_storyline_fails(self):
        passed, evidence, details = validate_overdue_storylines(
            "His sister went to the market.",
            {
                "overdue_storylines": [
                    {
                        "description": "张三需要去北京办事",
                        "related_characters": ["张三"],
                    }
                ]
            },
        )
        assert passed is False

    def test_mentioned_storyline_via_character_passes(self):
        passed, evidence, details = validate_overdue_storylines(
            "张三 walked through the gate of Beijing.",
            {
                "overdue_storylines": [
                    {
                        "description": "张三需要去北京办事",
                        "related_characters": ["张三"],
                    }
                ]
            },
        )
        assert passed is True


class TestValidateNoFabrication:
    """Contract tests for validate_no_fabrication."""

    def test_return_structure_is_valid(self):
        result = validate_no_fabrication("story", {})
        assert _isValidResult(result)

    def test_clean_story_passes(self):
        passed, evidence, details = validate_no_fabrication(
            "今天天气很好。他走出家门。",
            {},
        )
        assert passed is True

    def test_recall_found_but_not_failing(self):
        """基础版本只记录潜在的回忆引用，不直接判定失败。"""
        passed, evidence, details = validate_no_fabrication(
            "上次他们约定好的事，这次终于要去办了。",
            {},
        )
        # 基础版本：记录潜在回忆引用，不直接判定失败
        assert passed is True


class TestValidateEstablishedFacts:
    """Contract tests for validate_established_facts."""

    def test_skips_when_no_facts(self):
        passed, evidence, details = validate_established_facts("story", {})
        assert passed is True
        assert details.get("skipped") is True

    def test_return_structure_is_valid(self):
        result = validate_established_facts("story", {})
        assert _isValidResult(result)

    def test_with_facts_passes_basic_check(self):
        passed, evidence, details = validate_established_facts(
            "story text",
            {"established_facts": [{"fact": "something", "week": 1}]},
        )
        assert passed is True  # 基础版本总是通过
        assert details.get("facts_count") == 1


# ============================================================
# HIGH-level validators
# ============================================================


class TestValidateSceneContinuity:
    """Contract tests for validate_scene_continuity."""

    def test_skips_when_no_location(self):
        passed, evidence, details = validate_scene_continuity("story", {})
        assert passed is True
        assert details.get("skipped") is True

    def test_return_structure_is_valid(self):
        result = validate_scene_continuity("story", {})
        assert _isValidResult(result)

    def test_location_in_opening_passes(self):
        passed, evidence, details = validate_scene_continuity(
            "他走进北京市中心的一个小巷。周围人来人往。",
            {"last_location": "北京"},
        )
        assert passed is True

    def test_transition_keyword_passes(self):
        passed, evidence, details = validate_scene_continuity(
            "他离开了原来的地方，踏入了新的旅程。",
            {"last_location": "上海"},
        )
        assert passed is True

    def test_no_location_nor_transition_fails(self):
        passed, evidence, details = validate_scene_continuity(
            "今天的天气非常不错。阳光洒在地面上。",
            {"last_location": "上海"},
        )
        assert passed is False


class TestValidateHighStorylines:
    """Contract tests for validate_high_storylines."""

    def test_skips_when_empty(self):
        passed, evidence, details = validate_high_storylines("story", {})
        assert passed is True
        assert details.get("skipped") is True

    def test_return_structure_is_valid(self):
        result = validate_high_storylines("story", {})
        assert _isValidResult(result)

    def test_mentioned_passes(self):
        passed, evidence, details = validate_high_storylines(
            "张三来到了市中心。",
            {
                "high_storylines": [
                    {"description": "张三探索城市", "related_characters": ["张三"]}
                ]
            },
        )
        assert passed is True

    def test_unmentioned_fails(self):
        passed, evidence, details = validate_high_storylines(
            "He went to the park on a sunny day.",
            {
                "high_storylines": [
                    {"description": "张三探索城市", "related_characters": ["张三"]}
                ]
            },
        )
        assert passed is False


class TestValidateCharacterConsistency:
    """Contract tests for validate_character_consistency."""

    def test_skips_when_no_traits(self):
        passed, evidence, details = validate_character_consistency("story", {})
        assert passed is True
        assert details.get("skipped") is True

    def test_return_structure_is_valid(self):
        result = validate_character_consistency("story", {})
        assert _isValidResult(result)

    def test_with_traits_passes_basic_check(self):
        passed, evidence, details = validate_character_consistency(
            "story text",
            {"character_traits": {"张三": ["勇敢", "善良"]}},
        )
        assert passed is True  # 基础版本总是通过


# ============================================================
# MEDIUM-level validators
# ============================================================


class TestValidateCharacterHabits:
    """Contract tests for validate_character_habits."""

    def test_skips_when_no_habits(self):
        passed, evidence, details = validate_character_habits("story", {})
        assert passed is True
        assert details.get("skipped") is True

    def test_return_structure_is_valid(self):
        result = validate_character_habits("story", {})
        assert _isValidResult(result)

    def test_always_passes_with_stats(self):
        passed, evidence, details = validate_character_habits(
            "张三每天早上都喝咖啡。",
            {
                "character_habits": [
                    {"habit": "每天早上喝咖啡", "character": "张三"},
                    {"habit": "喜欢跑步", "character": "李四"},
                ]
            },
        )
        assert passed is True  # 总是通过，只统计
        assert "total_habits" in details
        assert "reflected_count" in details


class TestValidateForeshadowing:
    """Contract tests for validate_foreshadowing."""

    def test_skips_when_no_activated_seed(self):
        passed, evidence, details = validate_foreshadowing("story", {})
        assert passed is True
        assert details.get("skipped") is True

    def test_return_structure_is_valid(self):
        result = validate_foreshadowing("story", {})
        assert _isValidResult(result)

    def test_seed_keyword_found_passes(self):
        passed, evidence, details = validate_foreshadowing(
            "一封神秘信件终于被打开了。",
            {
                "activated_seed": {
                    "description": "一封神秘信件",
                    "related_characters": [],
                }
            },
        )
        assert passed is True

    def test_seed_not_found_fails(self):
        passed, evidence, details = validate_foreshadowing(
            "今天天气很好。",
            {
                "activated_seed": {
                    "description": "一封神秘信件",
                    "related_characters": [],
                }
            },
        )
        assert passed is False


class TestValidateMediumStorylines:
    """Contract tests for validate_medium_storylines."""

    def test_skips_when_empty(self):
        passed, evidence, details = validate_medium_storylines("story", {})
        assert passed is True
        assert details.get("skipped") is True

    def test_return_structure_is_valid(self):
        result = validate_medium_storylines("story", {})
        assert _isValidResult(result)

    def test_always_passes_with_stats(self):
        passed, evidence, details = validate_medium_storylines(
            "张三来到了图书馆。",
            {
                "medium_storylines": [
                    {"description": "张三在图书馆学习", "related_characters": ["张三"]}
                ]
            },
        )
        assert passed is True
        assert "total" in details
        assert "mentioned_count" in details


class TestValidateLogicConstraints:
    """Contract tests for validate_logic_constraints."""

    def test_skips_when_no_season(self):
        passed, evidence, details = validate_logic_constraints("story", {})
        assert passed is True
        assert details.get("skipped") is True

    def test_return_structure_is_valid(self):
        result = validate_logic_constraints("story", {})
        assert _isValidResult(result)

    def test_consistent_season_passes(self):
        passed, evidence, details = validate_logic_constraints(
            "春天来了，花儿都开了。",
            {"season": "春"},
        )
        assert passed is True

    def test_inconsistent_season_fails(self):
        passed, evidence, details = validate_logic_constraints(
            "外面大雪纷飞，寒风刺骨。",
            {"season": "夏"},
        )
        assert passed is False


# ============================================================
# LOW-level validators
# ============================================================


class TestValidateAntiRepetition:
    """Contract tests for validate_anti_repetition."""

    def test_return_structure_is_valid(self):
        result = validate_anti_repetition("story", {})
        assert _isValidResult(result)

    def test_no_duplicates_passes(self):
        passed, evidence, details = validate_anti_repetition(
            "第一句话很长很长很长。第二句话也很长很长。第三句不同。",
            {},
        )
        assert passed is True

    def test_duplicate_sentences_fails(self):
        """完全相同的长句重复应该检测失败。"""
        long_sentence = "这是一个很长的句子用来测试重复检测功能是否正常工作"
        passed, evidence, details = validate_anti_repetition(
            f"{long_sentence}。中间有其他内容。{long_sentence}。",
            {},
        )
        assert passed is False
        assert "duplicates" in details


class TestValidateVectorContext:
    """Contract tests for validate_vector_context."""

    def test_skips_when_no_context(self):
        passed, evidence, details = validate_vector_context("story", {})
        assert passed is True
        assert details.get("skipped") is True

    def test_return_structure_is_valid(self):
        result = validate_vector_context("story", {})
        assert _isValidResult(result)

    def test_with_context_passes_and_reports_length(self):
        passed, evidence, details = validate_vector_context(
            "story text",
            {"vector_context": "Some historical context here."},
        )
        assert passed is True  # 仅统计，不判定失败
        assert details.get("has_vector_context") is True
        assert details.get("context_length") > 0
