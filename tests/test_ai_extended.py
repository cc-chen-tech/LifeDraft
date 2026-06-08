"""Tests for remaining AI modules: option_generator, story_analyzer, story_generator, story_rewriter, summary_generator, generator facade."""

import json
from unittest.mock import Mock, patch

import pytest

from src.ai.models import EventOption, GameEvent

# ==================== OptionGenerator Tests ====================


class TestOptionGenerator:
    """Test OptionGenerator class."""

    def _make_generator(self, mock_client=None):
        from src.ai.option_generator import OptionGenerator

        return OptionGenerator(mock_client or Mock())

    def test_generate_options_success(self):
        """Test successful option generation."""
        mock_client = Mock()
        mock_client.call.return_value = json.dumps(
            {
                "options": [
                    {
                        "text": "选项A",
                        "effects": {
                            "energy": -5,
                            "mood": 10,
                            "knowledge": 0,
                            "wealth": 0,
                        },
                    },
                    {
                        "text": "选项B",
                        "effects": {
                            "energy": 0,
                            "mood": 0,
                            "knowledge": 10,
                            "wealth": 0,
                        },
                    },
                    {
                        "text": "选项C",
                        "effects": {
                            "energy": -2,
                            "mood": 2,
                            "knowledge": 3,
                            "wealth": 0,
                        },
                    },
                ]
            }
        )
        gen = self._make_generator(mock_client)
        event = gen.generate_options_only("故事描述", {"age": 22}, language="zh")
        assert event.event_description == "故事描述"
        assert len(event.options) == 3
        assert event.options[0].text == "选项A"

    def test_generate_options_rejects_two_options_and_returns_three_contextual_fallbacks(self):
        """Two options is a production regression: the UI expects three meaningful choices."""
        mock_client = Mock()
        mock_client.call.return_value = json.dumps(
            {
                "options": [
                    {"text": "陪晓雨去吃麻辣烫", "effects": {"energy": -10, "mood": 10}},
                    {"text": "直接回家搭框架", "effects": {"energy": -15, "knowledge": 10}},
                ]
            }
        )
        gen = self._make_generator(mock_client)

        event = gen.generate_options_only(
            "顾晨曦和陈晓雨讨论用户调研框架，准备把客服数据写进里程碑计划。",
            {},
            language="zh",
            retry_count=1,
        )

        assert len(event.options) == 3
        assert {opt.text for opt in event.options}.isdisjoint(
            {"回应眼前的请求", "先核对现场线索", "积极面对新的一天", "保持平常心继续前进"}
        )

    def test_generate_options_fallback(self):
        """Test fallback options when all retries fail."""
        mock_client = Mock()
        mock_client.call.side_effect = Exception("API error")
        gen = self._make_generator(mock_client)
        event = gen.generate_options_only("Story text", {}, language="zh", retry_count=2)
        assert len(event.options) == 3
        assert "积极面对" not in event.options[0].text

    def test_generate_options_fallback_en(self):
        """Test English fallback options."""
        mock_client = Mock()
        mock_client.call.side_effect = Exception("fail")
        gen = self._make_generator(mock_client)
        event = gen.generate_options_only("Story", {}, language="en", retry_count=1)
        assert len(event.options) == 3
        assert "request" not in event.options[0].text.lower()

    def test_generate_options_invalid_json_then_fallback(self):
        """Test options generation when JSON has <2 options."""
        mock_client = Mock()
        mock_client.call.return_value = json.dumps(
            {"options": [{"text": "Only one", "effects": {"energy": 0}}]}
        )
        gen = self._make_generator(mock_client)
        event = gen.generate_options_only("Story", {}, retry_count=1)
        # Falls back to default options
        assert len(event.options) == 3

    def test_validate_and_fix_relationships_no_settings(self):
        """Test validation with no character settings."""
        gen = self._make_generator()
        event = GameEvent(
            event_description="test",
            options=[
                EventOption(text="A", effects={"relationships": {"Unknown": 5}}),
                EventOption(text="B", effects={"energy": -5}),
            ],
        )
        gen.validate_and_fix_relationships(event, None)
        # No error, no change

    def test_validate_and_fix_relationships_exact_match(self):
        """Test validation keeps valid names."""
        gen = self._make_generator()
        event = GameEvent(
            event_description="test",
            options=[
                EventOption(text="A", effects={"relationships": {"张三": 5}}),
                EventOption(text="B", effects={"energy": -5}),
            ],
        )
        settings = {"relationships": {"key_people": [{"name": "张三"}]}}
        gen.validate_and_fix_relationships(event, settings)
        assert "张三" in event.options[0].effects["relationships"]

    def test_validate_and_fix_relationships_case_insensitive(self):
        """Test case-insensitive name matching."""
        gen = self._make_generator()
        event = GameEvent(
            event_description="test",
            options=[
                EventOption(text="A", effects={"relationships": {"john": 5}}),
                EventOption(text="B", effects={"energy": -5}),
            ],
        )
        settings = {"relationships": {"key_people": [{"name": "John"}]}}
        gen.validate_and_fix_relationships(event, settings)
        assert "John" in event.options[0].effects["relationships"]

    def test_validate_and_fix_relationships_role_match(self):
        """Test name matching by role."""
        gen = self._make_generator()
        event = GameEvent(
            event_description="test",
            options=[
                EventOption(text="A", effects={"relationships": {"老师": 5}}),
                EventOption(text="B", effects={"energy": -5}),
            ],
        )
        settings = {"relationships": {"key_people": [{"name": "李华", "role": "老师"}]}}
        gen.validate_and_fix_relationships(event, settings)
        assert "李华" in event.options[0].effects["relationships"]

    def test_validate_and_fix_relationships_keeps_non_key_people(self):
        """Test non-key_people names are kept as-is (not dropped or mapped)."""
        gen = self._make_generator()
        event = GameEvent(
            event_description="test",
            options=[
                EventOption(text="A", effects={"relationships": {"韦待价": 5}}),
                EventOption(text="B", effects={"energy": -5}),
            ],
        )
        settings = {"relationships": {"key_people": [{"name": "张三"}, {"name": "李四"}]}}
        gen.validate_and_fix_relationships(event, settings)
        # Non-key_people name should be kept as-is, not dropped or mapped
        assert "韦待价" in event.options[0].effects["relationships"]
        assert event.options[0].effects["relationships"]["韦待价"] == 5

    def test_validate_and_fix_relationships_no_cross_mapping(self):
        """Test non-key_people names are NOT mapped to key_people.

        Previously, step 4 would map unmatched names to the nearest key_people
        in story text. This was removed because it creates semantically wrong
        relationship effects (e.g., effect for 武承嗣 incorrectly applied to 裴行俭).
        Now non-key_people names are kept as-is.
        """
        gen = self._make_generator()
        event = GameEvent(
            event_description="武承嗣在朝堂上与裴行俭争论不休，气氛十分紧张。",
            options=[
                EventOption(text="A", effects={"relationships": {"武承嗣": -5}}),
                EventOption(text="B", effects={"energy": -5}),
            ],
        )
        settings = {"relationships": {"key_people": [{"name": "裴行俭"}, {"name": "李四"}]}}
        gen.validate_and_fix_relationships(event, settings)
        # 武承嗣 should be kept as-is, NOT mapped to 裴行俭
        assert "武承嗣" in event.options[0].effects["relationships"]
        assert event.options[0].effects["relationships"]["武承嗣"] == -5
        assert "裴行俭" not in event.options[0].effects["relationships"]

    def test_validate_and_fix_relationships_family_members(self):
        """Test family members are also valid relationship targets."""
        gen = self._make_generator()
        event = GameEvent(
            event_description="test",
            options=[
                EventOption(text="A", effects={"relationships": {"母亲王氏": 5}}),
                EventOption(text="B", effects={"energy": -5}),
            ],
        )
        settings = {
            "relationships": {"key_people": [{"name": "张三"}]},
            "family": {"family_members": [{"name": "母亲王氏", "role": "母亲"}]},
        }
        gen.validate_and_fix_relationships(event, settings)
        assert "母亲王氏" in event.options[0].effects["relationships"]

    def test_validate_event_quality_adds_action_points(self):
        """Test quality validation adds missing action_points."""
        gen = self._make_generator()
        event = GameEvent(
            event_description="test",
            options=[
                EventOption(text="A", effects={"energy": -5, "mood": 10}),
                EventOption(text="B", effects={"energy": 5, "mood": -5}),
            ],
        )
        gen.validate_event_quality(event)
        assert event.options[0].effects["action_points"] == -1

    def test_validate_event_quality_too_few_options(self):
        """Test quality validation rejects <2 options."""
        gen = self._make_generator()
        # Create a mock event with only 1 option to bypass Pydantic validation
        mock_event = Mock()
        mock_event.options = [EventOption(text="Only one", effects={})]
        with pytest.raises(ValueError, match="at least 2"):
            gen.validate_event_quality(mock_event)

    def test_validate_options_consistency_character_in_story_text(self):
        """Test characters appearing in story text are allowed in relationships."""
        gen = self._make_generator()
        story_text = "今天遇到了清虚真人，他教会了我很多道理。"
        event = GameEvent(
            event_description="测试故事",
            options=[
                EventOption(text="A", effects={"relationships": {"清虚真人": 10}}),
                EventOption(text="B", effects={"energy": -5}),
            ],
        )
        # 清虚真人 not in available_people, but in story text
        available_people = ["张三", "李四"]
        issues = gen.validate_options_consistency(
            event, story_text, available_people, language="zh"
        )
        # Should NOT have warning for 清虚真人
        assert not any("清虚真人" in issue for issue in issues)

    def test_validate_options_consistency_generic_name_allowed(self):
        """Test generic names are allowed in relationships."""
        gen = self._make_generator()
        story_text = "测试故事"
        event = GameEvent(
            event_description="测试故事",
            options=[
                EventOption(text="A", effects={"relationships": {"同事": 5, "朋友": -5}}),
                EventOption(text="B", effects={"energy": -5}),
            ],
        )
        available_people = ["张三"]
        issues = gen.validate_options_consistency(
            event, story_text, available_people, language="zh"
        )
        # Generic names should NOT trigger warnings
        assert not any("同事" in issue for issue in issues)
        assert not any("朋友" in issue for issue in issues)

    def test_validate_options_consistency_unknown_character_warning(self):
        """Test unknown characters not in story text generate warnings."""
        gen = self._make_generator()
        story_text = "测试故事"
        event = GameEvent(
            event_description="测试故事",
            options=[
                EventOption(text="A", effects={"relationships": {"陌生人甲": 5}}),
                EventOption(text="B", effects={"energy": -5}),
            ],
        )
        available_people = ["张三"]
        issues = gen.validate_options_consistency(
            event, story_text, available_people, language="zh"
        )
        # Should have warning for 陌生人甲
        assert any("陌生人甲" in issue for issue in issues)

    def test_validate_options_consistency_known_character_no_warning(self):
        """Test known characters in available_people generate no warnings."""
        gen = self._make_generator()
        story_text = "测试故事"
        event = GameEvent(
            event_description="测试故事",
            options=[
                EventOption(text="A", effects={"relationships": {"张三": 5}}),
                EventOption(text="B", effects={"energy": -5}),
            ],
        )
        available_people = ["张三", "李四"]
        issues = gen.validate_options_consistency(
            event, story_text, available_people, language="zh"
        )
        # Should NOT have warning for 张三
        assert not any("张三" in issue for issue in issues)


# ==================== StoryAnalyzer Tests ====================


class TestDynamicFact:
    """Test DynamicFact dataclass."""

    def test_to_dict_and_from_dict(self):
        from src.ai.story_analyzer import DynamicFact

        fact = DynamicFact(
            fact_id="f_test_1",
            fact_type="physical_state",
            subject="张三",
            description="受伤了",
            constraint_text="不能跑步",
            source_week=5,
            importance="critical",
        )
        d = fact.to_dict()
        assert d["fact_id"] == "f_test_1"
        assert d["importance"] == "critical"

        restored = DynamicFact.from_dict(d)
        assert restored.fact_id == fact.fact_id
        assert restored.constraint_text == fact.constraint_text

    def test_from_dict_with_defaults(self):
        from src.ai.story_analyzer import DynamicFact

        fact = DynamicFact.from_dict({})
        assert fact.fact_id == ""
        assert fact.expiry_week == -1
        assert fact.active is True


class TestStoryAnalyzer:
    """Test StoryAnalyzer class."""

    def test_analyze_empty_story(self):
        from src.ai.story_analyzer import StoryAnalyzer

        analyzer = StoryAnalyzer(Mock())
        result = analyzer.analyze_story("", "choice", [], 1, {}, "zh")
        assert result == []

    def test_analyze_story_success(self):
        from src.ai.story_analyzer import StoryAnalyzer

        mock_client = Mock()
        mock_client.call.return_value = json.dumps(
            {
                "facts": [
                    {
                        "action": "new",
                        "fact_type": "physical_state",
                        "subject": "张三",
                        "description": "右臂骨折",
                        "constraint_text": "不能提重物",
                        "importance": "critical",
                        "expiry_week": 10,
                        "related_entities": ["医院"],
                    }
                ]
            }
        )
        analyzer = StoryAnalyzer(mock_client)
        results = analyzer.analyze_story(
            "张三在事故中受伤了",
            "去医院",
            [],
            5,
            {"relationships": {"key_people": [{"name": "张三"}]}},
            "zh",
        )
        assert len(results) == 1
        assert results[0].subject == "张三"
        assert results[0].importance == "critical"

    def test_analyze_story_failure(self):
        from src.ai.story_analyzer import StoryAnalyzer

        mock_client = Mock()
        mock_client.call.side_effect = Exception("API error")
        analyzer = StoryAnalyzer(mock_client)
        result = analyzer.analyze_story("story", "choice", [], 1, {}, "zh")
        assert result == []

    def test_parse_update_action(self):
        from src.ai.story_analyzer import DynamicFact, StoryAnalyzer

        analyzer = StoryAnalyzer(Mock())
        existing = [
            DynamicFact(
                fact_id="f_old",
                fact_type="physical_state",
                subject="张三",
                description="受伤",
                constraint_text="不能跑步",
                active=True,
            )
        ]
        response = json.dumps(
            {
                "facts": [
                    {
                        "action": "update",
                        "target_fact_id": "f_old",
                        "fact_type": "physical_state",
                        "subject": "张三",
                        "description": "伤势好转",
                        "constraint_text": "可以慢跑了",
                    }
                ]
            }
        )
        results = analyzer._parse_analysis_response(response, 10, existing)
        assert len(results) == 1
        assert results[0].supersedes == "f_old"

    def test_parse_invalidate_action(self):
        from src.ai.story_analyzer import DynamicFact, StoryAnalyzer

        analyzer = StoryAnalyzer(Mock())
        existing = [
            DynamicFact(
                fact_id="f_old",
                fact_type="test",
                subject="A",
                description="d",
                constraint_text="c",
                active=True,
            )
        ]
        response = json.dumps(
            {
                "facts": [
                    {
                        "action": "invalidate",
                        "target_fact_id": "f_old",
                        "subject": "A",
                        "description": "d",
                    }
                ]
            }
        )
        analyzer._parse_analysis_response(response, 10, existing)
        assert existing[0].active is False

    def test_build_existing_facts_context_zh(self):
        from src.ai.story_analyzer import DynamicFact, StoryAnalyzer

        analyzer = StoryAnalyzer(Mock())
        facts = [
            DynamicFact(
                fact_type="test",
                subject="张三",
                description="有伤",
                constraint_text="别跑",
                active=True,
            )
        ]
        ctx = analyzer._build_existing_facts_context(facts, "zh")
        assert "当前已记录" in ctx
        assert "张三" in ctx

    def test_build_existing_facts_context_en(self):
        from src.ai.story_analyzer import DynamicFact, StoryAnalyzer

        analyzer = StoryAnalyzer(Mock())
        facts = [
            DynamicFact(
                fact_type="test",
                subject="John",
                description="injured",
                constraint_text="no running",
                active=True,
            )
        ]
        ctx = analyzer._build_existing_facts_context(facts, "en")
        assert "Currently Recorded" in ctx

    def test_build_empty_context(self):
        from src.ai.story_analyzer import StoryAnalyzer

        analyzer = StoryAnalyzer(Mock())
        assert analyzer._build_existing_facts_context([], "zh") == ""

    def test_parse_duplicate_id(self):
        """Test ID deduplication when new fact has same ID as existing."""
        from src.ai.story_analyzer import DynamicFact, StoryAnalyzer

        analyzer = StoryAnalyzer(Mock())
        existing = [
            DynamicFact(
                fact_id="f_张三_physical__w5",
                fact_type="physical_state",
                subject="张三",
                description="old",
            )
        ]
        response = json.dumps(
            {
                "facts": [
                    {
                        "action": "new",
                        "fact_type": "physical_state",
                        "subject": "张三",
                        "description": "new",
                        "constraint_text": "constraint",
                    }
                ]
            }
        )
        results = analyzer._parse_analysis_response(response, 5, existing)
        assert len(results) == 1
        assert results[0].fact_id != "f_张三_physical__w5"


# ==================== StoryGenerator Tests ====================


class TestStoryGenerator:
    """Test StoryGenerator class."""

    def test_get_phase_early_career(self):
        from src.ai.story_generator import StoryGenerator

        assert StoryGenerator._get_phase_from_state({"week": 0}) == "early_career"
        assert StoryGenerator._get_phase_from_state({"week": 23}) == "early_career"

    def test_get_phase_establishing(self):
        from src.ai.story_generator import StoryGenerator

        assert StoryGenerator._get_phase_from_state({"week": 24}) == "establishing"
        assert StoryGenerator._get_phase_from_state({"week": 47}) == "establishing"

    def test_get_phase_growth(self):
        from src.ai.story_generator import StoryGenerator

        assert StoryGenerator._get_phase_from_state({"week": 48}) == "growth"

    def test_get_phase_consolidation(self):
        from src.ai.story_generator import StoryGenerator

        assert StoryGenerator._get_phase_from_state({"week": 72}) == "consolidation"
        assert StoryGenerator._get_phase_from_state({"week": 96}) == "consolidation"

    @patch("src.ai.story_generator.get_round_event_prompt", return_value="prompt")
    @patch("src.ai.story_generator.get_system_prompt", return_value="sys")
    def test_generate_round_event_fallback(self, mock_sys, mock_prompt):
        """Test round event falls back on error."""
        from src.ai.story_generator import StoryGenerator

        mock_client = Mock()
        mock_client.call.side_effect = Exception("API error")
        gen = StoryGenerator(mock_client)
        event = gen.generate_round_event(
            player_state={"week": 0, "age": 22, "decision_history": []},
            language="zh",
            round_number=0,
            round_context="",
            option_generator=Mock(),
        )
        assert len(event.options) == 3
        assert "平静" in event.event_description
        assert {opt.text for opt in event.options}.isdisjoint(
            {"回应眼前的请求", "先核对现场线索", "积极面对新的一天", "保持平常心继续前进"}
        )

    @patch("src.ai.story_generator.get_round_event_prompt", return_value="prompt")
    @patch("src.ai.story_generator.get_system_prompt", return_value="sys")
    def test_generate_round_event_option_failure_uses_three_contextual_fallbacks(
        self, mock_sys, mock_prompt
    ):
        """If story succeeds but option validation fails, keep story and build 3 non-generic choices."""
        from src.ai.story_generator import StoryGenerator

        story = "顾晨曦在浙大实验室拿到合作协议，需要和林一凡确认技术对接计划。"
        mock_client = Mock()
        mock_client.call.return_value = story
        option_generator = Mock()
        option_generator.generate_options_only.side_effect = ValueError("generic options")

        event = StoryGenerator(mock_client).generate_round_event(
            player_state={"week": 2, "age": 26, "decision_history": []},
            language="zh",
            round_number=2,
            round_context="",
            option_generator=option_generator,
        )

        assert event.event_description == story
        assert len(event.options) == 3
        assert {opt.text for opt in event.options}.isdisjoint(
            {"回应眼前的请求", "先核对现场线索", "积极面对新的一天", "保持平常心继续前进"}
        )

    @patch("src.ai.story_generator.get_round_event_prompt", return_value="prompt")
    @patch("src.ai.story_generator.get_system_prompt", return_value="sys")
    def test_generate_round_event_en_fallback(self, mock_sys, mock_prompt):
        """Test English round event fallback."""
        from src.ai.story_generator import StoryGenerator

        mock_client = Mock()
        mock_client.call.side_effect = Exception("fail")
        gen = StoryGenerator(mock_client)
        event = gen.generate_round_event(
            player_state={"week": 0},
            language="en",
            round_number=0,
            round_context="",
            option_generator=Mock(),
        )
        assert len(event.options) == 3
        assert "dramatic turn" in event.event_description.lower()


# ==================== StoryRewriter Tests ====================


class TestStoryRewriter:
    """Test StoryRewriter class."""

    def test_rewrite_segment_success(self):
        from src.ai.story_rewriter import StoryRewriter

        mock_client = Mock()
        mock_client.call.return_value = "Rewritten story content"
        rewriter = StoryRewriter(mock_client)
        result = rewriter.rewrite_story_segment(
            "Original story",
            "segment to replace",
            "Make it funnier",
            None,
            "",
            language="zh",
        )
        assert result == "Rewritten story content"

    def test_rewrite_segment_failure(self):
        from src.ai.story_rewriter import StoryRewriter

        mock_client = Mock()
        mock_client.call.side_effect = Exception("fail")
        rewriter = StoryRewriter(mock_client)
        result = rewriter.rewrite_story_segment("Original", "segment", "instruction", None, "")
        assert result == "Original"

    @patch("src.ai.story_rewriter.get_story_only_prompt", return_value="prompt")
    def test_regenerate_story_success(self, mock_prompt):
        from src.ai.story_rewriter import StoryRewriter

        mock_client = Mock()
        mock_client.call.return_value = "New story text"
        rewriter = StoryRewriter(mock_client)
        result = rewriter.regenerate_story({"week": 0}, None, "", language="zh")
        assert result == "New story text"

    @patch("src.ai.story_rewriter.get_story_only_prompt", return_value="prompt")
    def test_regenerate_story_failure_zh(self, mock_prompt):
        from src.ai.story_rewriter import StoryRewriter

        mock_client = Mock()
        mock_client.call.side_effect = Exception("fail")
        rewriter = StoryRewriter(mock_client)
        result = rewriter.regenerate_story({"week": 0}, None, "", language="zh")
        assert "失败" in result

    @patch("src.ai.story_rewriter.get_story_only_prompt", return_value="prompt")
    def test_regenerate_story_failure_en(self, mock_prompt):
        from src.ai.story_rewriter import StoryRewriter

        mock_client = Mock()
        mock_client.call.side_effect = Exception("fail")
        rewriter = StoryRewriter(mock_client)
        result = rewriter.regenerate_story({"week": 0}, None, "", language="en")
        assert "Failed" in result

    @patch("src.ai.story_rewriter.get_story_only_prompt", return_value="prompt")
    def test_regenerate_with_context(self, mock_prompt):
        from src.ai.story_rewriter import StoryRewriter

        mock_client = Mock()
        mock_client.call.return_value = "Contextual story"
        rewriter = StoryRewriter(mock_client)
        result = rewriter.regenerate_story({"week": 0}, None, "Previous context", language="zh")
        assert result == "Contextual story"

    @patch("src.ai.story_rewriter.get_story_only_prompt", return_value="prompt")
    def test_regenerate_phase_detection(self, mock_prompt):
        """Test phase detection in regenerate_story."""
        from src.ai.story_rewriter import StoryRewriter

        mock_client = Mock()
        mock_client.call.return_value = "story"
        rewriter = StoryRewriter(mock_client)
        # week 72+ = consolidation
        rewriter.regenerate_story({"week": 80}, None, "")
        # Should not raise

    @patch("src.ai.story_rewriter.get_story_only_prompt", return_value="prompt")
    def test_regenerate_derives_last_event(self, mock_prompt):
        """Test regeneration derives last_event_description from decision_history."""
        from src.ai.story_rewriter import StoryRewriter

        mock_client = Mock()
        mock_client.call.return_value = "story"
        rewriter = StoryRewriter(mock_client)
        result = rewriter.regenerate_story(
            {"week": 5, "decision_history": [{"event": "Last event happened"}]},
            None,
            "",
        )
        assert result == "story"


# ==================== SummaryGenerator Tests ====================


class TestSummaryGenerator:
    """Test SummaryGenerator class."""

    def test_compress_story_success(self):
        from src.ai.summary_generator import SummaryGenerator

        mock_client = Mock()
        mock_client.call.return_value = json.dumps(
            {
                "summary": "压缩后的摘要",
                "storyline_updates": [{"type": "continue"}],
                "fact_updates": [],
                "event_concluded": True,
                "foreshadowing_seeds": [],
                "habit_updates": [],
            }
        )
        gen = SummaryGenerator(mock_client)
        result = gen.compress_story("Long story text", "选择A", "zh")
        assert result["summary"] == "压缩后的摘要"
        assert result["event_concluded"] is True

    def test_compress_story_truncates_long_summary(self):
        from src.ai.summary_generator import SummaryGenerator

        mock_client = Mock()
        mock_client.call.return_value = json.dumps(
            {
                "summary": "x" * 800,
            }
        )
        gen = SummaryGenerator(mock_client)
        result = gen.compress_story("story", "choice", "zh")
        assert len(result["summary"]) <= 700

    def test_compress_story_failure_fallback(self):
        from src.ai.summary_generator import SummaryGenerator

        mock_client = Mock()
        mock_client.call.side_effect = Exception("fail")
        gen = SummaryGenerator(mock_client)
        result = gen.compress_story("A story that is long enough " * 5, "choice", "zh")
        assert "summary" in result
        assert result["event_concluded"] is True

    def test_compress_story_short_fallback(self):
        from src.ai.summary_generator import SummaryGenerator

        mock_client = Mock()
        mock_client.call.side_effect = Exception("fail")
        gen = SummaryGenerator(mock_client)
        result = gen.compress_story("Short", "choice", "zh")
        assert result["summary"] == "Short"

    def test_clean_summary_text_code_block(self):
        from src.ai.summary_generator import SummaryGenerator

        assert SummaryGenerator._clean_summary_text("```json\nSummary text\n```") == "Summary text"

    def test_clean_summary_text_json_prefix(self):
        from src.ai.summary_generator import SummaryGenerator

        assert (
            "summary"
            not in SummaryGenerator._clean_summary_text('{"summary": "Clean text"}')
            .lower()
            .split()[:1]
        )

    def test_clean_summary_text_empty(self):
        from src.ai.summary_generator import SummaryGenerator

        assert SummaryGenerator._clean_summary_text("") == ""
        assert SummaryGenerator._clean_summary_text(None) is None

    def test_clean_summary_text_quotes(self):
        from src.ai.summary_generator import SummaryGenerator

        result = SummaryGenerator._clean_summary_text('"Hello world"')
        assert result == "Hello world"

    def test_extract_summary_from_raw_regex(self):
        from src.ai.summary_generator import SummaryGenerator

        content = '{"summary": "Extracted text", "other": "data"}'
        result = SummaryGenerator._extract_summary_from_raw(content, "original", "zh")
        assert result == "Extracted text"

    def test_extract_summary_from_raw_malformed(self):
        from src.ai.summary_generator import SummaryGenerator

        content = "Just some plain text that is long enough to be used"
        result = SummaryGenerator._extract_summary_from_raw(content, "original", "zh")
        assert len(result) > 0

    def test_extract_summary_fallback_to_original(self):
        from src.ai.summary_generator import SummaryGenerator

        content = "ab"  # Too short
        result = SummaryGenerator._extract_summary_from_raw(content, "original story text", "zh")
        assert result == "original story text"

    def test_generate_weekly_summary_success(self):
        from src.ai.summary_generator import SummaryGenerator

        mock_client = Mock()
        mock_client.call.return_value = json.dumps(
            {"summary": "本周很忙碌", "bonus_effects": {"energy": 5, "mood": 3}}
        )
        gen = SummaryGenerator(mock_client)
        result = gen.generate_weekly_summary([{"summary": "round1"}], {}, "zh")
        assert result["summary"] == "本周很忙碌"
        assert result["bonus_effects"]["energy"] == 5

    def test_generate_weekly_summary_invalid_bonus_clamped(self):
        from src.ai.summary_generator import SummaryGenerator

        mock_client = Mock()
        mock_client.call.return_value = json.dumps(
            {
                "summary": "Summary",
                "bonus_effects": {"energy": 50, "mood": "invalid", "knowledge": 10},
            }
        )
        gen = SummaryGenerator(mock_client)
        result = gen.generate_weekly_summary([], {}, "zh")
        assert "energy" not in result["bonus_effects"]  # 50 > 20, excluded
        assert result["bonus_effects"]["knowledge"] == 10

    def test_generate_weekly_summary_fallback(self):
        from src.ai.summary_generator import SummaryGenerator

        mock_client = Mock()
        mock_client.call.side_effect = Exception("fail")
        gen = SummaryGenerator(mock_client)
        result = gen.generate_weekly_summary([], {}, "zh")
        assert "平静" in result["summary"]

    def test_generate_four_week_summary_success(self):
        from src.ai.summary_generator import SummaryGenerator

        mock_client = Mock()
        mock_client.call_with_retry.return_value = "四周总结文本"
        gen = SummaryGenerator(mock_client)
        result = gen.generate_four_week_summary(["s1", "s2"], [{"choice": "A"}])
        assert result == "四周总结文本"

    def test_generate_four_week_summary_fallback(self):
        from src.ai.summary_generator import SummaryGenerator

        mock_client = Mock()
        mock_client.call_with_retry.side_effect = Exception("fail")
        gen = SummaryGenerator(mock_client)
        result = gen.generate_four_week_summary([], [], language="zh")
        assert "平静" in result

    def test_generate_yearly_summary_success(self):
        from src.ai.summary_generator import SummaryGenerator

        mock_client = Mock()
        mock_client.call_with_retry.return_value = "年度总结"
        gen = SummaryGenerator(mock_client)
        result = gen.generate_yearly_summary([{"summary": "s"}])
        assert result == "年度总结"

    def test_generate_yearly_summary_fallback(self):
        from src.ai.summary_generator import SummaryGenerator

        mock_client = Mock()
        mock_client.call_with_retry.side_effect = Exception("fail")
        gen = SummaryGenerator(mock_client)
        result = gen.generate_yearly_summary([], language="en")
        assert "experiences" in result.lower()


# ==================== EventGenerator Facade Tests ====================


class TestEventGeneratorFacade:
    """Test EventGenerator facade class."""

    @patch("src.ai.generator.AIClient")
    @patch("src.ai.generator.EventCache")
    def test_init_creates_subservices(self, mock_cache_cls, mock_ai_cls):
        from src.ai.generator import EventGenerator

        gen = EventGenerator(api_key="test-key")
        assert gen.story_gen is not None
        assert gen.option_gen is not None
        assert gen.summary_gen is not None
        assert gen.rewriter is not None

    @patch("src.ai.generator.AIClient")
    def test_init_no_cache(self, mock_ai_cls):
        from src.ai.generator import EventGenerator

        gen = EventGenerator(api_key="test-key", use_cache=False)
        assert gen.cache is None

    @patch("src.ai.generator.AIClient")
    @patch("src.ai.generator.EventCache")
    def test_get_phase_from_state_delegation(self, mock_cache, mock_ai):
        from src.ai.generator import EventGenerator

        assert EventGenerator._get_phase_from_state({"week": 0}) == "early_career"
        assert EventGenerator._get_phase_from_state({"week": 72}) == "consolidation"

    @patch("src.ai.generator.AIClient")
    @patch("src.ai.generator.EventCache")
    def test_clean_summary_delegation(self, mock_cache, mock_ai):
        from src.ai.generator import EventGenerator

        result = EventGenerator._clean_summary_text("```json\nText\n```")
        assert "```" not in result

    @patch("src.ai.generator.AIClient")
    @patch("src.ai.generator.EventCache")
    def test_generate_completion(self, mock_cache, mock_ai_cls):
        from src.ai.generator import EventGenerator

        gen = EventGenerator(api_key="test-key")
        gen.ai_client.call.return_value = "Completion result"
        result = gen.generate_completion("prompt")
        assert result == "Completion result"

    @patch("src.ai.generator.AIClient")
    @patch("src.ai.generator.EventCache")
    def test_generate_completion_json(self, mock_cache, mock_ai_cls):
        from src.ai.generator import EventGenerator

        gen = EventGenerator(api_key="test-key")
        gen.ai_client.call_json.return_value = {"key": "value"}
        result = gen.generate_completion_json("prompt")
        assert result == {"key": "value"}

    @patch("src.ai.generator.AIClient")
    @patch("src.ai.generator.EventCache")
    def test_compress_story_delegation(self, mock_cache, mock_ai_cls):
        from src.ai.generator import EventGenerator

        gen = EventGenerator(api_key="test-key")
        gen.summary_gen.compress_story = Mock(return_value={"summary": "test"})
        result = gen.compress_story("story", "choice", "zh")
        assert result["summary"] == "test"

    @patch("src.ai.generator.AIClient")
    @patch("src.ai.generator.EventCache")
    def test_load_preset_events_empty(self, mock_cache, mock_ai_cls):
        from src.ai.generator import EventGenerator

        with patch("builtins.open", side_effect=FileNotFoundError):
            gen = EventGenerator(api_key="test-key")
            assert gen.preset_events == {} or isinstance(gen.preset_events, dict)
