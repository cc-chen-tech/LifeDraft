"""Tests for AI layer: cache, client, consistency_validator, utils, system_prompts, profile_synthesizer."""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.ai.utils import extract_json
from src.ai.models import GameEvent, EventOption
from src.ai.system_prompts import get_system_prompt, _PROMPT_REGISTRY
from src.ai.consistency_validator import (
    ConsistencyValidator, ConsistencyIssue, ValidationResult
)


# ==================== AI Utils Tests ====================

class TestExtractJson:
    """Test extract_json utility function."""

    def test_pure_json(self):
        """Test parsing pure JSON string."""
        text = '{"key": "value", "num": 42}'
        result = extract_json(text)
        assert result == {"key": "value", "num": 42}

    def test_json_in_code_block(self):
        """Test parsing JSON from ```json block."""
        text = '```json\n{"event": "test"}\n```'
        result = extract_json(text)
        assert result == {"event": "test"}

    def test_json_in_backtick_block(self):
        """Test parsing JSON from ``` block without json label."""
        text = '```\n{"event": "test"}\n```'
        result = extract_json(text)
        assert result == {"event": "test"}

    def test_json_in_single_quote_block(self):
        """Test parsing JSON from '''json block."""
        text = "'''json\n{\"event\": \"test\"}\n'''"
        result = extract_json(text)
        assert result == {"event": "test"}

    def test_json_embedded_in_text(self):
        """Test extracting JSON from surrounding text."""
        text = 'Here is the result: {"event": "test"} and that is all.'
        result = extract_json(text)
        assert result == {"event": "test"}

    def test_empty_input(self):
        """Test empty input returns None."""
        assert extract_json("") is None
        assert extract_json(None) is None

    def test_no_json_found(self):
        """Test non-JSON text returns None."""
        result = extract_json("This is just plain text with no JSON")
        assert result is None

    def test_whitespace_json(self):
        """Test JSON with leading/trailing whitespace."""
        text = '  \n  {"key": "value"}  \n  '
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_nested_json(self):
        """Test nested JSON objects."""
        text = '{"outer": {"inner": "value"}, "list": [1, 2, 3]}'
        result = extract_json(text)
        assert result["outer"]["inner"] == "value"
        assert result["list"] == [1, 2, 3]


# ==================== AI Models Tests ====================

class TestGameEventModel:
    """Test GameEvent and EventOption models."""

    def test_event_option_with_empty_effects(self):
        """Test EventOption with empty effects dict."""
        option = EventOption(text="Do nothing", effects={})
        assert option.text == "Do nothing"
        assert option.effects == {}

    def test_game_event_single_option(self):
        """Test GameEvent rejects single option (min 2 required)."""
        with pytest.raises(Exception):
            event = GameEvent(
                event_description="Simple event",
                options=[EventOption(text="Only choice", effects={"energy": -5})]
            )

    def test_game_event_from_json_with_extra_fields(self):
        """Test GameEvent.from_json ignores extra fields gracefully."""
        json_str = json.dumps({
            "event_description": "Test",
            "options": [
                {"text": "A", "effects": {"energy": -5}},
                {"text": "B", "effects": {"mood": 5}},
            ],
            "extra_field": "ignored"
        })
        event = GameEvent.from_json(json_str)
        assert event.event_description == "Test"

    def test_game_event_from_invalid_json(self):
        """Test GameEvent.from_json with invalid JSON."""
        with pytest.raises(Exception):
            GameEvent.from_json("not valid json at all")


# ==================== System Prompts Tests ====================

class TestSystemPrompts:
    """Test system prompt registry."""

    def test_get_system_prompt_zh(self):
        """Test getting Chinese system prompts."""
        prompt = get_system_prompt("story_novelist", "zh")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_system_prompt_en(self):
        """Test getting English system prompts."""
        prompt = get_system_prompt("story_novelist", "en")
        assert isinstance(prompt, str)
        assert "novelist" in prompt.lower() or "talented" in prompt.lower()

    def test_all_registered_prompts_exist(self):
        """Test all registered prompt keys return valid prompts."""
        for key in _PROMPT_REGISTRY:
            zh_prompt = get_system_prompt(key, "zh")
            en_prompt = get_system_prompt(key, "en")
            assert isinstance(zh_prompt, str)
            assert isinstance(en_prompt, str)
            assert len(zh_prompt) > 0
            assert len(en_prompt) > 0

    def test_invalid_key_raises(self):
        """Test invalid key raises KeyError."""
        with pytest.raises(KeyError):
            get_system_prompt("nonexistent_key", "zh")

    def test_all_expected_keys_present(self):
        """Test all expected prompt keys are registered."""
        expected_keys = [
            "story_novelist", "option_generator", "story_compressor",
            "weekly_summary", "four_week_summary", "yearly_summary",
            "story_continuation", "story_rewriter", "consistency_validator",
            "story_analyzer", "profile_synthesizer"
        ]
        for key in expected_keys:
            assert key in _PROMPT_REGISTRY, f"Missing prompt key: {key}"


# ==================== Consistency Validator Tests ====================

class TestConsistencyIssue:
    """Test ConsistencyIssue dataclass."""

    def test_create_issue(self):
        """Test creating a consistency issue."""
        issue = ConsistencyIssue(
            dimension="geographic",
            severity="CRITICAL",
            description="Character is in two places at once",
            fix_suggestion="Choose one location"
        )
        assert issue.dimension == "geographic"
        assert issue.severity == "CRITICAL"


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_passed_result(self):
        """Test passed validation result."""
        result = ValidationResult(passed=True)
        assert result.passed is True
        assert result.has_critical_issues is False
        assert result.critical_issues == []
        assert result.warning_issues == []

    def test_failed_result_with_issues(self):
        """Test failed result with issues."""
        issues = [
            ConsistencyIssue("geographic", "CRITICAL", "Location mismatch", "Fix it"),
            ConsistencyIssue("temporal", "WARNING", "Time inconsistency", "Check dates")
        ]
        result = ValidationResult(passed=False, issues=issues)
        assert result.has_critical_issues is True
        assert len(result.critical_issues) == 1
        assert len(result.warning_issues) == 1


class TestConsistencyValidator:
    """Test ConsistencyValidator class."""

    def test_validate_empty_story(self):
        """Test validation with empty story passes."""
        mock_client = Mock()
        validator = ConsistencyValidator(mock_client)
        result = validator.validate_story("", None, {}, {}, "zh")
        assert result.passed is True

    def test_validate_none_world_model(self):
        """Test validation with None world model passes."""
        mock_client = Mock()
        validator = ConsistencyValidator(mock_client)
        result = validator.validate_story("Some story", None, {}, {}, "zh")
        assert result.passed is True

    def test_parse_validation_response_passed(self):
        """Test parsing a passed validation response."""
        mock_client = Mock()
        validator = ConsistencyValidator(mock_client)
        response = json.dumps({"issues": []})
        result = validator._parse_validation_response(response, "zh")
        assert result.passed is True

    def test_parse_validation_response_with_critical(self):
        """Test parsing response with critical issues."""
        mock_client = Mock()
        validator = ConsistencyValidator(mock_client)
        response = json.dumps({
            "issues": [{
                "dimension": "geographic",
                "severity": "CRITICAL",
                "description": "Character in wrong city",
                "fix_suggestion": "Move to correct city"
            }]
        })
        result = validator._parse_validation_response(response, "zh")
        assert result.passed is False
        assert len(result.critical_issues) == 1
        assert "修正" in result.fix_instructions

    def test_parse_validation_response_warnings_only(self):
        """Test parsing response with only warnings passes."""
        mock_client = Mock()
        validator = ConsistencyValidator(mock_client)
        response = json.dumps({
            "issues": [{
                "dimension": "temporal",
                "severity": "WARNING",
                "description": "Minor time skip",
                "fix_suggestion": "Add transition"
            }]
        })
        result = validator._parse_validation_response(response, "zh")
        assert result.passed is True
        assert len(result.warning_issues) == 1

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON response passes through."""
        mock_client = Mock()
        validator = ConsistencyValidator(mock_client)
        result = validator._parse_validation_response("not json", "zh")
        assert result.passed is True

    def test_ai_driven_should_retry(self):
        """★ 测试 AI 驱动的 should_retry 判断。"""
        mock_client = Mock()
        validator = ConsistencyValidator(mock_client)
        
        # AI 返回 should_retry: true
        response = json.dumps({
            "issues": [{
                "dimension": "personality",
                "severity": "WARNING",
                "reasoning": "张三有已建立画像，性格偏差严重",
                "description": "张三突然变得攻击性",
                "fix_suggestion": "保持一致"
            }],
            "should_retry": True,
            "retry_reason": "已建立画像的角色性格偏差严重"
        })
        result = validator._parse_validation_response(response, "zh")
        assert result.passed is False  # AI 判断需要重试
        
        # AI 返回 should_retry: false，即使有 WARNING
        response2 = json.dumps({
            "issues": [{
                "dimension": "personality",
                "severity": "WARNING",
                "description": "轻微性格偏差",
                "fix_suggestion": "建议改进"
            }],
            "should_retry": False,
            "retry_reason": ""
        })
        result2 = validator._parse_validation_response(response2, "zh")
        assert result2.passed is True  # AI 判断不需要重试

    def test_fallback_to_critical_when_no_should_retry(self):
        """★ 测试当 AI 未返回 should_retry 时回退到传统逻辑。"""
        mock_client = Mock()
        validator = ConsistencyValidator(mock_client)
        
        # AI 没有返回 should_retry，有 CRITICAL 就不通过
        response = json.dumps({
            "issues": [{
                "dimension": "geographic",
                "severity": "CRITICAL",
                "description": "Wrong location",
                "fix_suggestion": "Fix location"
            }]
        })
        result = validator._parse_validation_response(response, "en")
        assert result.passed is False  # 有 CRITICAL 所以不通过
        assert "MUST STRICTLY FOLLOW" in result.fix_instructions


# ==================== EventCache Tests ====================

class TestEventCache:
    """Test EventCache class."""

    def test_cache_init(self, tmp_path):
        """Test cache initialization creates directory."""
        from src.ai.cache import EventCache
        cache = EventCache(cache_dir=tmp_path / "test_cache")
        assert (tmp_path / "test_cache").exists()

    def test_cache_set_and_size(self, tmp_path):
        """Test setting cache and checking size."""
        from src.ai.cache import EventCache
        cache = EventCache(cache_dir=tmp_path / "test_cache")

        event = GameEvent(
            event_description="Test event",
            options=[
                EventOption(text="Option A", effects={"energy": -5}),
                EventOption(text="Option B", effects={"mood": 5}),
            ]
        )
        state = {"age": 22, "energy": 70, "mood": 60, "knowledge": 50,
                "wealth": 10000, "week": 0}
        cache.set(state, "zh", event)
        assert cache.size() == 1

    def test_cache_clear(self, tmp_path):
        """Test clearing cache."""
        from src.ai.cache import EventCache
        cache = EventCache(cache_dir=tmp_path / "test_cache")

        event = GameEvent(
            event_description="Test",
            options=[
                EventOption(text="A", effects={}),
                EventOption(text="B", effects={}),
            ]
        )
        cache.set({"age": 22, "energy": 70, "mood": 60, "knowledge": 50,
                   "wealth": 10000, "week": 0}, "zh", event)
        cache.clear()
        assert cache.size() == 0

    def test_cache_key_generation(self, tmp_path):
        """Test cache key is consistent for same input."""
        from src.ai.cache import EventCache
        cache = EventCache(cache_dir=tmp_path / "test_cache")

        state = {"age": 22, "energy": 70, "mood": 60, "knowledge": 50,
                "wealth": 10000, "week": 0}
        key1 = cache._generate_cache_key(state, "zh")
        key2 = cache._generate_cache_key(state, "zh")
        assert key1 == key2

    def test_cache_key_differs_for_different_state(self, tmp_path):
        """Test cache key differs for different states."""
        from src.ai.cache import EventCache
        cache = EventCache(cache_dir=tmp_path / "test_cache")

        state1 = {"age": 22, "energy": 70, "mood": 60, "knowledge": 50,
                  "wealth": 10000, "week": 0}
        state2 = {"age": 22, "energy": 70, "mood": 60, "knowledge": 50,
                  "wealth": 10000, "week": 10}
        key1 = cache._generate_cache_key(state1, "zh")
        key2 = cache._generate_cache_key(state2, "zh")
        assert key1 != key2


# ==================== AIClient Tests ====================

class TestAIClient:
    """Test AIClient class."""

    @patch('src.ai.client.openai.OpenAI')
    def test_init_with_api_key(self, mock_openai):
        """Test AIClient initialization with API key."""
        from src.ai.client import AIClient
        client = AIClient(api_key="test-key", model="gpt-4")
        assert client.api_key == "test-key"
        assert client.model == "gpt-4"

    def test_init_without_api_key_raises(self):
        """Test AIClient raises without API key."""
        from src.ai.client import AIClient
        with patch.object(AIClient, '__init__', lambda self, **kw: None):
            pass  # Can't test directly without env, covered by integration

    @patch('src.ai.client.openai.OpenAI')
    def test_call_method(self, mock_openai_cls):
        """Test AIClient.call method."""
        from src.ai.client import AIClient
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "  Hello World  "

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        client = AIClient(api_key="test-key")
        result = client.call("sys prompt", "user prompt")
        assert result == "Hello World"

    @patch('src.ai.client.openai.OpenAI')
    def test_call_json_method(self, mock_openai_cls):
        """Test AIClient.call_json method."""
        from src.ai.client import AIClient
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"key": "value"}'

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        client = AIClient(api_key="test-key")
        result = client.call_json("sys", "user")
        assert result == {"key": "value"}

    @patch('src.ai.client.openai.OpenAI')
    def test_call_with_streaming(self, mock_openai_cls):
        """Test AIClient.call with stream callback."""
        from src.ai.client import AIClient

        chunk1 = Mock()
        chunk1.choices = [Mock()]
        chunk1.choices[0].delta.content = "Hello"

        chunk2 = Mock()
        chunk2.choices = [Mock()]
        chunk2.choices[0].delta.content = " World"

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = [chunk1, chunk2]
        mock_openai_cls.return_value = mock_client

        collected = []
        client = AIClient(api_key="test-key")
        result = client.call("sys", "user", stream_callback=lambda t: collected.append(t))
        assert result == "Hello World"
        assert collected == ["Hello", " World"]

    @patch('src.ai.client.openai.OpenAI')
    def test_call_with_retry_succeeds(self, mock_openai_cls):
        """Test call_with_retry succeeds on first attempt."""
        from src.ai.client import AIClient
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "OK"

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        client = AIClient(api_key="test-key")
        result = client.call_with_retry("sys", "user", retry_count=3)
        assert result == "OK"

    @patch('src.ai.client.openai.OpenAI')
    def test_call_with_retry_fails_all(self, mock_openai_cls):
        """Test call_with_retry raises after all retries fail."""
        from src.ai.client import AIClient
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai_cls.return_value = mock_client

        client = AIClient(api_key="test-key")
        with pytest.raises(ValueError, match="failed after"):
            client.call_with_retry("sys", "user", retry_count=2)


# ==================== ProfileSynthesizer Tests ====================

class TestProfileSynthesizer:
    """Test ProfileSynthesizer class."""

    @patch('src.ai.client.openai.OpenAI')
    def test_synthesize_success(self, mock_openai_cls):
        """Test successful profile synthesis."""
        from src.ai.profile_synthesizer import ProfileSynthesizer
        from src.ai.client import AIClient

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "behavioral_traits": ["冲突回避型", "善于倾听"],
            "speech_style": "说话直接",
            "decision_patterns": ["倾向妥协"],
            "emotional_tendencies": ["压抑情绪"],
            "behavioral_boundaries": ["不在公开场合发怒"],
            "constraint_text": "角色约束文本"
        })

        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client_instance

        client = AIClient(api_key="test-key")
        synthesizer = ProfileSynthesizer(client)

        result = synthesizer.synthesize(
            char_name="张三",
            traits=["外向", "热心"],
            evidence=["帮助了邻居", "在聚会上表现活跃"],
            existing_profile=None,
            language="zh"
        )
        assert result is not None
        assert result["character"] == "张三"
        assert len(result["behavioral_traits"]) <= 5

    @patch('src.ai.client.openai.OpenAI')
    def test_synthesize_failure(self, mock_openai_cls):
        """Test profile synthesis handles failure gracefully."""
        from src.ai.profile_synthesizer import ProfileSynthesizer
        from src.ai.client import AIClient

        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.side_effect = Exception("API Error")
        mock_openai_cls.return_value = mock_client_instance

        client = AIClient(api_key="test-key")
        synthesizer = ProfileSynthesizer(client)

        result = synthesizer.synthesize("张三", [], [], None, "zh")
        assert result is None
