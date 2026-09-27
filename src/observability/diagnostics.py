"""Bounded metadata-only lifecycle diagnostics shared by workers and requests."""
from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .request_context import RequestContext, current_request_context, request_context, resolve_request_id

IDENTITY_FIELDS = frozenset({"request_id", "operation_id", "feature", "operation", "user_id", "game_id", "job_id", "job_type", "segment_index", "attempt_id"})
SAFE_FIELDS = IDENTITY_FIELDS | frozenset({
    "attempt", "max_attempts", "event_id", "revision", "batch_id", "slot_index", "asset_id",
    "error_code", "provider_code", "provider_trace_id", "retryable", "finding_codes", "severity",
    "disposition", "duration_ms", "size_bytes", "count", "persisted", "used_fallback", "reason",
    "recovery_count", "selected_image_id", "http_status", "status", "provider", "model",
    "evidence_key_id",
})
_TOKEN = re.compile(r"^[A-Za-z0-9_.:/-]{1,160}$")


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str) and _TOKEN.fullmatch(value):
        return value
    if isinstance(value, (list, tuple)):
        return [item for item in (_safe(v) for v in value[:64]) if item is not None]
    return None


def context_metadata() -> Dict[str, Any]:
    context = current_request_context()
    return {k: v for k, v in asdict(context).items() if v is not None} if context else {}


@contextmanager
def diagnostic_context(**fields: Any) -> Iterator[RequestContext]:
    current = current_request_context() or RequestContext(request_id=resolve_request_id(None))
    updates = {k: _safe(v) for k, v in fields.items() if k in IDENTITY_FIELDS}
    with request_context(replace(current, **updates)) as context:
        yield context


def exception_metadata(error: Optional[BaseException]) -> Dict[str, Any]:
    if error is None:
        return {}
    result: Dict[str, Any] = {"exception_type": type(error).__name__, "exception_frames": []}
    seen: set[int] = set()
    current: Optional[BaseException] = error
    while current is not None and id(current) not in seen and len(seen) < 8:
        seen.add(id(current))
        result["root_exception_type"] = type(current).__name__
        tb = current.__traceback__
        while tb is not None:
            result["exception_frames"].append({
                "file": Path(tb.tb_frame.f_code.co_filename).name,
                "function": tb.tb_frame.f_code.co_name,
                "line": tb.tb_lineno,
            })
            tb = tb.tb_next
        for key, attrs in {
            "provider_code": ("provider_code", "code"),
            "provider_trace_id": ("provider_trace_id", "trace_id"),
            "retryable": ("retryable",), "http_status": ("status_code", "http_status"),
        }.items():
            for attr in attrs:
                value = _safe(getattr(current, attr, None))
                if value is not None:
                    result.setdefault(key, value)
                    break
        response_status = _safe(getattr(getattr(current, "response", None), "status_code", None))
        if response_status is not None:
            result.setdefault("http_status", response_status)
        current = current.__cause__ or current.__context__
    result["exception_frames"] = result["exception_frames"][-32:]
    return result


def emit_diagnostic(event: str, *, phase: str, outcome: str, error: Optional[BaseException] = None, **fields: Any) -> Dict[str, Any]:
    payload = {"event": _safe(event) or "diagnostic", "phase": _safe(phase), "outcome": _safe(outcome), **context_metadata()}
    payload.update({k: _safe(v) for k, v in fields.items() if k in SAFE_FIELDS and _safe(v) is not None})
    # Only authenticated ciphertext may cross this explicit evidence boundary.
    encrypted = fields.get("encrypted_evidence")
    if event == "story_validation_evidence" and isinstance(encrypted, str) and re.fullmatch(r"[A-Za-z0-9_=-]{80,32768}", encrypted):
        payload["encrypted_evidence"] = encrypted
    payload.update(exception_metadata(error))
    logging.getLogger("diagnostic").log(
        logging.WARNING if outcome in {"failed", "failure", "error"} else logging.INFO,
        payload["event"], extra={**payload, "event_data": payload},
    )
    return payload
