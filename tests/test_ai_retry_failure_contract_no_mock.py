"""Deterministic provider-fake contracts for AI retry failure semantics."""

from __future__ import annotations

from typing import Any

import pytest

from src.ai.retry_handler import AIRetryHandler


class ScriptedProvider:
    """Small provider fake that records the public AIClient call contract."""

    def __init__(self, outcomes: list[object]):
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    def call(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return str(outcome)


def test_timeout_retry_injects_feedback_decays_temperature_and_stops_streaming() -> None:
    provider = ScriptedProvider([TimeoutError("provider deadline exceeded"), "recovered story"])
    handler = AIRetryHandler(provider)  # type: ignore[arg-type]
    streamed: list[str] = []
    on_stream = streamed.append

    result = handler.call_with_retry(
        system_prompt="system",
        user_prompt="write a story",
        retry_count=2,
        max_tokens=900,
        stream_callback=on_stream,
        language="en",
        model="deterministic-model",
    )

    assert result == "recovered story"
    assert [call["temperature"] for call in provider.calls] == [0.85, 0.7]
    assert provider.calls[0]["stream_callback"] is on_stream
    assert provider.calls[1]["stream_callback"] is None
    assert "provider deadline exceeded" in provider.calls[1]["user_prompt"]
    assert provider.calls[1]["model"] == "deterministic-model"


def test_json_retry_recovers_from_malformed_content_with_chinese_feedback() -> None:
    provider = ScriptedProvider(["not json", '{"choice":"保留这个选择"}'])
    handler = AIRetryHandler(provider)

    result = handler.call_with_json_retry(
        system_prompt="system",
        user_prompt="return json",
        retry_count=2,
        language="zh",
    )

    assert result == {"choice": "保留这个选择"}
    assert [call["temperature"] for call in provider.calls] == [0.85, 0.7]
    assert "Invalid JSON format" in provider.calls[1]["user_prompt"]
    assert "确保输出有效的JSON格式" in provider.calls[1]["user_prompt"]


def test_retry_exhaustion_includes_the_last_provider_failure() -> None:
    provider = ScriptedProvider([TimeoutError("first timeout"), RuntimeError("second failure")])
    handler = AIRetryHandler(provider)

    with pytest.raises(ValueError, match="second failure"):
        handler.call_with_retry(
            system_prompt="system",
            user_prompt="write a story",
            retry_count=2,
        )

    assert len(provider.calls) == 2
