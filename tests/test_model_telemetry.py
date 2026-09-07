import asyncio
import io
import json
import logging
import time

import pytest

from src.ai.budgets import GenerationBudgetExceeded
from src.observability.model_telemetry import (
    ModelCallContext,
    classify_model_error,
    configure_model_logging,
    emit_model_call,
    sanitize_error_message,
)


class _ProviderError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError("provider timed out"), "timeout"),
        (asyncio.TimeoutError("provider timed out"), "timeout"),
        (_ProviderError("rate limited", 429), "rate_limit"),
        (_ProviderError("upstream unavailable", 503), "provider_5xx"),
        (ValueError("invalid JSON output"), "invalid_output"),
        (GenerationBudgetExceeded("provider call budget exhausted"), "budget_exceeded"),
        (asyncio.CancelledError(), "cancelled"),
        (ValueError("OpenAI API key is required"), "unknown"),
        (RuntimeError("unexpected provider failure"), "unknown"),
    ],
)
def test_classify_model_error_uses_stable_categories(error, expected):
    assert classify_model_error(error) == expected


def test_sanitize_error_message_removes_credentials_and_bounds_length():
    secret = "sk-live-1234567890"
    message = (
        f"Authorization: Bearer {secret}; api_key={secret}; "
        + "prompt="
        + ("private story " * 80)
    )

    sanitized = sanitize_error_message(RuntimeError(message))

    assert secret not in sanitized
    assert "Bearer" not in sanitized
    assert len(sanitized) <= 240


def test_emit_model_call_returns_safe_event_and_logs_extra(caplog):
    context = ModelCallContext(
        request_id="req-1",
        operation_id="op-1",
        feature="story_generation",
        operation="continuation",
        phase="provider",
        provider="openai-compatible",
        model="deepseek-v4-flash",
        attempt=2,
        retry_index=1,
        fallback_from="deepseek-v4-pro",
    )

    with caplog.at_level(logging.INFO, logger="model"):
        event = emit_model_call(
            context,
            outcome="success",
            started_at=time.monotonic() - 0.01,
            streamed=True,
            usage={"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            logger=logging.getLogger("model"),
        )

    assert event["event"] == "model_call"
    assert event["schema_version"] == 1
    assert event["request_id"] == "req-1"
    assert event["operation_id"] == "op-1"
    assert event["attempt"] == 2
    assert event["retry_index"] == 1
    assert event["fallback_from"] == "deepseek-v4-pro"
    assert event["outcome"] == "success"
    assert event["total_tokens"] == 18
    assert event["token_usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }
    assert event["duration_ms"] >= 0
    assert "prompt" not in event
    assert "response" not in event
    assert caplog.records[-1].model_event == event


def test_emit_model_call_classifies_and_sanitizes_failure():
    event = emit_model_call(
        ModelCallContext(
            request_id="req-2",
            operation_id=None,
            feature="story_generation",
            operation="opening",
            phase="provider",
            provider="openai-compatible",
            model="deepseek-v4-flash",
        ),
        outcome="failure",
        started_at=time.monotonic(),
        error=_ProviderError("Authorization: Bearer sk-secret", 429),
        logger=logging.getLogger("model.failure.test"),
    )

    assert event["outcome"] == "failure"
    assert event["error_kind"] == "rate_limit"
    assert event["http_status"] == 429
    assert "sk-secret" not in event["error_message"]
    assert "Bearer" not in event["error_message"]


def test_configure_model_logging_emits_one_json_line_without_duplicate_handlers():
    stream = io.StringIO()
    logger = configure_model_logging(stream=stream)
    same_logger = configure_model_logging(stream=stream)

    logger.info(
        "model_call",
        extra={
            "model_event": {
                "event": "model_call",
                "schema_version": 1,
                "outcome": "success",
            }
        },
    )

    assert same_logger is logger
    assert len(logger.handlers) == 1
    lines = [line for line in stream.getvalue().splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "event": "model_call",
        "outcome": "success",
        "schema_version": 1,
    }
