"""Truncation recovery contract tests.

No mocks. Tests truncation detection and recovery with hand-rolled stubs.
"""

from src.ai.truncation_recovery import (TruncationRecovery,
                                        TruncationRecoveryConfig)


class FakeClient:
    """Stub client for testing recovery loops."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.calls = []
        self.index = 0

    def __call__(self, *, system_prompt, user_prompt, **kwargs):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "kwargs": kwargs,
            }
        )
        response = self.responses[self.index] if self.index < len(self.responses) else ""
        self.index += 1
        return response


class TestTruncationRecoveryContract:
    """Contract tests for truncation detection and recovery."""

    def test_detect_truncation_finish_reason_length(self):
        """finish_reason='length' should always be truncated."""
        tr = TruncationRecovery()
        assert tr.detect_truncation("any text", "length") is True

    def test_detect_truncation_finish_reason_stop(self):
        """finish_reason='stop' should not be truncated."""
        tr = TruncationRecovery()
        assert tr.detect_truncation("any text", "stop") is False

    def test_detect_truncation_none_finish_reason(self):
        """None finish_reason should not be truncated."""
        tr = TruncationRecovery()
        assert tr.detect_truncation("any text", None) is False

    def test_detect_truncation_cjk_no_punctuation(self):
        """CJK text ending without terminal punctuation is truncated."""
        tr = TruncationRecovery()
        assert tr.detect_truncation("这是一个未完成的句子", "stop") is True

    def test_detect_truncation_cjk_with_period(self):
        """CJK text ending with period is complete."""
        tr = TruncationRecovery()
        assert tr.detect_truncation("这是一个完成的句子。", "stop") is False

    def test_detect_truncation_cjk_with_exclamation(self):
        """CJK text ending with exclamation is complete."""
        tr = TruncationRecovery()
        assert tr.detect_truncation("太棒了！", "stop") is False

    def test_detect_truncation_cjk_with_question(self):
        """CJK text ending with question mark is complete."""
        tr = TruncationRecovery()
        assert tr.detect_truncation("为什么？", "stop") is False

    def test_detect_truncation_empty_string(self):
        """Empty string should not be truncated."""
        tr = TruncationRecovery()
        assert tr.detect_truncation("", "stop") is False

    def test_detect_truncation_english_no_punctuation(self):
        """English text without CJK should not trigger CJK heuristic."""
        tr = TruncationRecovery()
        assert tr.detect_truncation("This is some text", "stop") is False

    def test_build_continuation_prompt_zh(self):
        """Chinese continuation prompt should use zh instruction."""
        tr = TruncationRecovery()
        prompt = tr.build_continuation_prompt("original", "partial text", language="zh")
        assert "请从中断处继续输出" in prompt
        assert "partial text" in prompt

    def test_build_continuation_prompt_en(self):
        """English continuation prompt should use en instruction."""
        tr = TruncationRecovery()
        prompt = tr.build_continuation_prompt("original", "partial text", language="en")
        assert "Continue output from where it was cut off" in prompt
        assert "partial text" in prompt

    def test_build_continuation_prompt_truncates_tail(self):
        """Long partial response should be truncated to 500 chars."""
        tr = TruncationRecovery()
        long_partial = "x" * 1000
        prompt = tr.build_continuation_prompt("original", long_partial, language="zh")
        # Should contain the tail, not the full text
        assert len(prompt) < 600  # Tail + instructions should be reasonable

    def test_recover_single_continuation_completes(self):
        """Single continuation that ends with punctuation should stop."""
        tr = TruncationRecovery()
        fake = FakeClient(responses=[" continuation text."])

        result = tr.recover(
            client_call=fake,
            system_prompt="sys",
            original_prompt="original",
            partial_response="partial",
            language="zh",
        )

        assert result == "partial continuation text."
        assert len(fake.calls) == 1

    def test_recover_multiple_continuations(self):
        """Multiple continuations should be joined."""
        config = TruncationRecoveryConfig(max_continuations=3)
        tr = TruncationRecovery(config)
        fake = FakeClient(responses=[" first", " second", " third."])

        result = tr.recover(
            client_call=fake,
            system_prompt="sys",
            original_prompt="original",
            partial_response="partial",
            language="zh",
        )

        assert result == "partial first second third."
        assert len(fake.calls) == 3

    def test_recover_stops_on_complete_sentence(self):
        """Should stop early when continuation ends with terminal punctuation."""
        tr = TruncationRecovery()
        fake = FakeClient(responses=[" complete sentence.", " extra"])

        result = tr.recover(
            client_call=fake,
            system_prompt="sys",
            original_prompt="original",
            partial_response="partial",
            language="zh",
        )

        assert result == "partial complete sentence."
        assert len(fake.calls) == 1

    def test_recover_passes_system_prompt(self):
        """System prompt should be forwarded to client call."""
        tr = TruncationRecovery()
        fake = FakeClient(responses=[" done."])

        tr.recover(
            client_call=fake,
            system_prompt="custom-system",
            original_prompt="original",
            partial_response="partial",
            language="zh",
        )

        assert fake.calls[0]["system_prompt"] == "custom-system"

    def test_recover_removes_stream_callback(self):
        """stream_callback should be stripped from kwargs."""
        tr = TruncationRecovery()
        fake = FakeClient(responses=[" done."])

        def stream_cb(chunk):
            pass

        tr.recover(
            client_call=fake,
            system_prompt="sys",
            original_prompt="original",
            partial_response="partial",
            language="zh",
            stream_callback=stream_cb,
            temperature=0.7,
        )

        assert "stream_callback" not in fake.calls[0]["kwargs"]
        assert fake.calls[0]["kwargs"]["temperature"] == 0.7

    def test_default_config_values(self):
        """Default config should have sensible values."""
        config = TruncationRecoveryConfig()
        assert config.max_continuations == 3
        assert "继续输出" in config.continuation_prompt_zh
        assert "Continue output" in config.continuation_prompt_en

    def test_custom_config_max_continuations(self):
        """Custom config should respect max_continuations."""
        config = TruncationRecoveryConfig(max_continuations=1)
        tr = TruncationRecovery(config)
        fake = FakeClient(responses=[" one", " two"])

        result = tr.recover(
            client_call=fake,
            system_prompt="sys",
            original_prompt="original",
            partial_response="partial",
            language="zh",
        )

        assert len(fake.calls) == 1
        assert result == "partial one"
