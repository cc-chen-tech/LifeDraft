"""Structured, privacy-safe telemetry for provider model calls.

The model logger emits one JSON object per completed provider attempt.  The
event deliberately contains metadata only: prompts, responses, credentials,
and user-authored story content must never cross this boundary.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from logging import Handler, LogRecord
from typing import Any, Dict, Mapping, Optional, TextIO


@dataclass(frozen=True)
class ModelCallContext:
    """Stable identifiers and provider metadata for one attempt."""

    request_id: str
    operation_id: Optional[str]
    feature: str
    operation: str
    phase: str
    provider: str
    model: str
    attempt: int = 1
    retry_index: int = 0
    fallback_from: Optional[str] = None


@dataclass(frozen=True)
class ModelCallEvent:
    """JSON-safe terminal event for one provider attempt."""

    schema_version: int
    event: str
    timestamp: str
    request_id: str
    operation_id: Optional[str]
    feature: str
    operation: str
    phase: str
    provider: str
    model: str
    attempt: int
    retry_index: int
    fallback_from: Optional[str]
    outcome: str
    error_kind: Optional[str]
    http_status: Optional[int]
    duration_ms: float
    streamed: bool
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    token_usage: Optional[Dict[str, int]]
    finish_reason: Optional[str]
    output_size: Optional[int]
    error_message: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _status_code(error: BaseException) -> Optional[int]:
    value = getattr(error, "status_code", None)
    if value is None:
        response = getattr(error, "response", None)
        value = getattr(response, "status_code", None)
    return int(value) if isinstance(value, (int, float)) else None


def classify_model_error(error: BaseException) -> str:
    """Map provider and application errors to a stable low-cardinality kind."""

    if isinstance(error, (asyncio.CancelledError, GeneratorExit)):
        return "cancelled"

    try:
        from src.ai.budgets import GenerationBudgetError
    except ImportError:  # pragma: no cover - keeps the helper importable in isolation
        GenerationBudgetError = ()  # type: ignore[assignment]
    if GenerationBudgetError and isinstance(error, GenerationBudgetError):
        return "budget_exceeded"

    status_code = _status_code(error)
    if status_code == 429:
        return "rate_limit"
    if status_code is not None and status_code >= 500:
        return "provider_5xx"
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return "timeout"
    message = str(error).lower()
    if "api key" in message or "api_key" in message:
        return "unknown"
    if isinstance(error, ValueError):
        return "invalid_output"

    error_name = type(error).__name__.lower()
    if "contentinspection" in error_name or "invalidresponse" in error_name:
        return "invalid_output"

    category = str(getattr(error, "category", "")).lower()
    if category == "timeout":
        return "timeout"
    if category == "rate_limit":
        return "rate_limit"
    if category in {"upstream", "capacity"}:
        return "provider_5xx"
    if category in {"invalid_response", "invalid_output"}:
        return "invalid_output"

    if any(
        marker in message
        for marker in (
            "invalid audio",
            "no audio",
            "empty output",
            "did not include",
            "invalid response",
        )
    ):
        return "invalid_output"

    if "timeout" in error_name:
        return "timeout"
    if "cancel" in error_name:
        return "cancelled"
    if "ratelimit" in error_name or "rate_limit" in error_name:
        return "rate_limit"
    return "unknown"


def sanitize_error_message(error: BaseException) -> str:
    """Return a bounded diagnostic message without credentials or payload text.

    Provider exception messages are not trusted: even after credential
    redaction, an upstream error may echo request content.  Keep the detailed
    text available to local debugging only and use the exception type as the
    production-safe message.
    """

    _ = str(error)  # Intentionally do not persist untrusted provider text.
    status_code = _status_code(error)
    suffix = f" status={status_code}" if status_code is not None else ""
    return f"{type(error).__name__}{suffix}"[:240]


def retry_feedback_message(error: BaseException) -> str:
    """Return bounded, redacted detail for internal retry feedback.

    Retry prompts and raised application errors still need actionable provider
    detail.  This is deliberately separate from ``sanitize_error_message``:
    terminal telemetry must remain type/status-only, while retry behavior must
    preserve stable provider diagnostics without carrying credentials or large
    payloads.
    """

    message = str(error).strip() or type(error).__name__
    message = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", message)
    message = re.sub(
        r"(?i)(api[_-]?key|authorization|token|secret)\s*[=:]\s*\S+",
        r"\1=[redacted]",
        message,
    )
    message = re.sub(r"\bsk-[A-Za-z0-9_-]+\b", "[redacted]", message)
    return " ".join(message.split())[:240]


def _usage_value(usage: Any, name: str) -> Optional[int]:
    value = usage.get(name) if isinstance(usage, Mapping) else getattr(usage, name, None)
    return int(value) if isinstance(value, (int, float)) else None


def _token_usage(usage: Any) -> Optional[Dict[str, int]]:
    if usage is None:
        return None
    values = {
        name: _usage_value(usage, name)
        for name in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        )
    }
    return {name: value for name, value in values.items() if value is not None}


def _json_safe_event(event: ModelCallEvent) -> Dict[str, Any]:
    # Round only for stable human inspection; preserve sub-millisecond values as
    # zero rather than emitting a negative duration from a clock adjustment.
    payload = event.to_dict()
    payload["duration_ms"] = max(0.0, round(float(payload["duration_ms"]), 2))
    json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return payload


def emit_model_call(
    context: ModelCallContext,
    outcome: str,
    started_at: float,
    *,
    error: Optional[BaseException] = None,
    usage: Any = None,
    streamed: bool = False,
    finish_reason: Optional[str] = None,
    output_size: Optional[int] = None,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """Emit and return one terminal event for a provider attempt."""

    status_code = _status_code(error) if error is not None else None
    event = ModelCallEvent(
        schema_version=1,
        event="model_call",
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        request_id=context.request_id,
        operation_id=context.operation_id,
        feature=context.feature,
        operation=context.operation,
        phase=context.phase,
        provider=context.provider,
        model=context.model,
        attempt=context.attempt,
        retry_index=context.retry_index,
        fallback_from=context.fallback_from,
        outcome=outcome,
        error_kind=classify_model_error(error) if error is not None else None,
        http_status=status_code,
        duration_ms=(time.monotonic() - started_at) * 1000,
        streamed=streamed,
        prompt_tokens=_usage_value(usage, "prompt_tokens") if usage is not None else None,
        completion_tokens=(
            _usage_value(usage, "completion_tokens") if usage is not None else None
        ),
        total_tokens=_usage_value(usage, "total_tokens") if usage is not None else None,
        token_usage=_token_usage(usage),
        finish_reason=finish_reason,
        output_size=output_size,
        error_message=sanitize_error_message(error) if error is not None else None,
    )
    payload = _json_safe_event(event)
    (logger or logging.getLogger("model")).info(
        "model_call",
        extra={"model_event": payload},
    )
    return payload


class _JsonLineFormatter(logging.Formatter):
    def format(self, record: LogRecord) -> str:
        payload = getattr(record, "model_event", None)
        if payload is None:
            payload = {"event": record.getMessage()}
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_model_logging(stream: Optional[TextIO] = None) -> logging.Logger:
    """Configure the dedicated model logger exactly once for JSONL output."""

    logger = logging.getLogger("model")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler: Optional[Handler] = next(
        (
            item
            for item in logger.handlers
            if getattr(item, "_model_json_handler", False)
        ),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler(stream or sys.stdout)
        handler._model_json_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    elif stream is not None and getattr(handler, "stream", None) is not stream:
        handler.setStream(stream)  # type: ignore[attr-defined]
    handler.setFormatter(_JsonLineFormatter())
    return logger
