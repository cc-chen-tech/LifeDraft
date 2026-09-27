"""Bounded, encrypted rejection evidence in the existing rotating app log.

Plaintext is available only to the operator decryptor with the application key.
Never include whole prompts, responses, credentials, or arbitrary object fields.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from typing import Any, Mapping, Sequence

from cryptography.fernet import Fernet, InvalidToken

from .diagnostics import IDENTITY_FIELDS, context_metadata, emit_diagnostic


def _cipher() -> tuple[Fernet, str]:
    secret = os.environ.get("DIAGNOSTIC_EVIDENCE_KEY") or os.environ.get("JWT_SECRET")
    if not secret:
        raise ValueError("validation evidence key missing")
    derived = hashlib.sha256(b"story2.validation-evidence.v1\0" + secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(derived)), hashlib.sha256(derived).hexdigest()[:12]


def _redact(value: Any, limit: int) -> str:
    text = str(value or "")[:8192]
    for name in ("OPENAI_API_KEY", "IMAGE_API_KEY", "MINIMAX_API_KEY", "JWT_SECRET", "DIAGNOSTIC_EVIDENCE_KEY"):
        secret = os.environ.get(name)
        if secret:
            text = text.replace(secret, "[redacted]")
    text = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", text)
    text = re.sub(r"(?i)(api[_-]?key|authorization|token|secret)\s*[=:]\s*\S+", r"\1=[redacted]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]+\b", "[redacted]", text)
    return text[:limit]


def emit_validation_evidence(
    phase: str, issues: Sequence[Mapping[str, Any]], *, story_text: str = "", **identity: Any,
) -> dict[str, Any]:
    """Log recoverable evidence, or an explicit failure without failing gameplay."""
    metadata = context_metadata()
    metadata.update({k: v for k, v in identity.items() if k in IDENTITY_FIELDS and v is not None})
    try:
        cipher, key_id = _cipher()
        details = []
        for issue in issues[:4]:
            entry = {name: _redact(issue.get(name), limit) for name, limit in {
                "code": 80, "severity": 24, "description": 320,
                "evidence": 160, "repair_instruction": 320,
            }.items()}
            evidence = str(issue.get("evidence") or "")[:160]
            offset = story_text.find(evidence) if evidence else -1
            entry["evidence_context"] = _redact(
                story_text[max(0, offset - 60):offset + len(evidence) + 60] if offset >= 0 else "", 240,
            )
            details.append(entry)
        document = {
            "schema_version": 1, **metadata, "phase": phase,
            "candidate_hash": hashlib.sha256(story_text.encode()).hexdigest() if story_text else None,
            "opening_excerpt": _redact(story_text[:160], 160),
            "ending_excerpt": _redact(story_text[-160:], 160),
            "issues": details, "truncated_issue_count": max(0, len(issues) - len(details)),
        }
        token = cipher.encrypt(json.dumps(document, ensure_ascii=False).encode()).decode()
        if len(token) > 32768:
            raise ValueError("validation evidence size limit")
        return emit_diagnostic(
            "story_validation_evidence", phase=phase, outcome="recorded", **metadata,
            evidence_key_id=key_id, encrypted_evidence=token, count=len(details),
        )
    except Exception as error:
        return emit_diagnostic(
            "story_validation_evidence", phase=phase, outcome="failed", **metadata,
            error=error, error_code="validation_evidence_unavailable",
        )


def decrypt_validation_evidence(
    payload: Mapping[str, Any], *, user_id: int, operation_id: str,
) -> dict[str, Any]:
    """Operator-only read: require both key possession and explicit identity."""
    if payload.get("user_id") != user_id or payload.get("operation_id") != operation_id:
        raise ValueError("evidence identity mismatch")
    cipher, key_id = _cipher()
    if payload.get("evidence_key_id") != key_id:
        raise ValueError("evidence key mismatch")
    token = payload.get("encrypted_evidence")
    if not isinstance(token, str) or len(token) > 32768:
        raise ValueError("invalid evidence token")
    try:
        result: dict[str, Any] = json.loads(cipher.decrypt(token.encode()))
    except (InvalidToken, ValueError) as error:
        raise ValueError("invalid evidence token") from error
    if result.get("user_id") != user_id or result.get("operation_id") != operation_id:
        raise ValueError("evidence identity mismatch")
    for name in IDENTITY_FIELDS:
        if payload.get(name) != result.get(name):
            raise ValueError("evidence identity mismatch")
    return result
