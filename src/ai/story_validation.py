"""Structured findings shared by story validation, retry, and UI diagnostics."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class FindingSeverity(str, Enum):
    HARD = "hard"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    severity: FindingSeverity
    confidence: float
    source: str
    message: str
    evidence: str = ""
    repair_instruction: str = ""
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        normalized_message = re.sub(r"\s+", " ", self.message).strip()
        normalized_evidence = re.sub(r"\s+", " ", self.evidence).strip()
        payload = "|".join(
            (
                self.code,
                self.severity.value,
                normalized_message,
                normalized_evidence,
            )
        )
        object.__setattr__(
            self,
            "fingerprint",
            hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16],
        )


def _legacy_code(message: str, severity: FindingSeverity) -> tuple[str, float]:
    lowered = message.lower()
    if "empty_story_output" in lowered:
        return "EMPTY_OUTPUT", 1.0
    if "缺少当天明确要求登场人物" in message:
        return "REQUIRED_CAST_MISSING", 1.0
    if "覆盖低于建议值" in message or "80%" in message:
        return "CAST_COVERAGE_LOW", 0.35
    if (
        "名单外命名角色" in message
        or "名单外关键角色" in message
        or "unapproved named person" in lowered
    ):
        return "HIGH_CONFIDENCE_UNKNOWN_PERSON", 0.95
    if "名单外人物" in message:
        return (
            "HIGH_CONFIDENCE_UNKNOWN_PERSON"
            if severity is FindingSeverity.HARD
            else "POSSIBLE_UNKNOWN_PERSON",
            0.85 if severity is FindingSeverity.HARD else 0.35,
        )
    if "预设关键人物" in message and (
        "完全没有" in message or "至少使用一个" in message
    ):
        return "REQUIRED_CAST_MISSING", 0.9
    if "story_too_" in lowered or "段落" in message or "篇幅" in message:
        return "INVALID_STORY_STRUCTURE", 1.0
    if "重复" in message or "duplicate" in lowered:
        return "REPEATED_CONTENT", 0.95
    return (
        "VALIDATION_FAILED" if severity is FindingSeverity.HARD else "QUALITY_WARNING",
        0.8 if severity is FindingSeverity.HARD else 0.4,
    )


def findings_from_legacy(
    *,
    issues: Iterable[str],
    warnings: Iterable[str],
    source: str,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for severity, messages in (
        (FindingSeverity.HARD, issues),
        (FindingSeverity.WARNING, warnings),
    ):
        for raw_message in messages:
            message = str(raw_message or "").strip()
            if not message:
                continue
            code, confidence = _legacy_code(message, severity)
            findings.append(
                ValidationFinding(
                    code=code,
                    severity=severity,
                    confidence=confidence,
                    source=source,
                    message=message,
                )
            )
    return findings
