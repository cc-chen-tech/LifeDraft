"""Errors and safe player-facing diagnostics for story generation failures."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Optional

from src.ai.story_validation import FindingSeverity, ValidationFinding


class GenerationFailureCode(str, Enum):
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    EMPTY_OUTPUT = "EMPTY_OUTPUT"
    INVALID_STORY_STRUCTURE = "INVALID_STORY_STRUCTURE"
    REQUIRED_CAST_MISSING = "REQUIRED_CAST_MISSING"
    HIGH_CONFIDENCE_UNKNOWN_PERSON = "HIGH_CONFIDENCE_UNKNOWN_PERSON"
    REPEATED_CONTENT = "REPEATED_CONTENT"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"


@dataclass(frozen=True)
class GenerationFailure:
    code: GenerationFailureCode
    summary: str
    detail: str
    retryable: bool
    attempts_used: int
    quality_level: str
    operation_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "summary": self.summary,
            "detail": self.detail,
            "retryable": self.retryable,
            "attempts_used": self.attempts_used,
            "quality_level": self.quality_level,
            "operation_id": self.operation_id,
        }


class StoryGenerationFailure(RuntimeError):
    """Raised when no valid round story can be generated."""

    def __init__(
        self,
        message: str,
        *,
        findings: Optional[Iterable[ValidationFinding]] = None,
        attempts_used: int = 0,
        failure_code: Optional[GenerationFailureCode] = None,
        circuit_break: bool = False,
    ) -> None:
        super().__init__(message)
        self.findings = tuple(findings or ())
        self.attempts_used = max(0, int(attempts_used))
        self.failure_code = failure_code
        self.circuit_break = bool(circuit_break)


class StoryRewriteFailure(RuntimeError):
    """Raised when a requested rewrite cannot be completed."""


class StoryContinuationFailure(RuntimeError):
    """Raised when a selected choice cannot produce a valid narrative outcome."""


_FAILURE_COPY = {
    GenerationFailureCode.PROVIDER_TIMEOUT: (
        "模型服务响应超时",
        "模型服务没有在单次请求时限内返回结果。失败稿没有保存，你可以再次生成。",
    ),
    GenerationFailureCode.EMPTY_OUTPUT: (
        "模型没有返回有效故事",
        "本次请求没有得到可用正文。失败结果没有保存，你可以再次生成。",
    ),
    GenerationFailureCode.INVALID_STORY_STRUCTURE: (
        "故事结构检查未通过",
        "正文篇幅、段落或选项结构不完整。失败稿没有保存，你可以再次生成。",
    ),
    GenerationFailureCode.REQUIRED_CAST_MISSING: (
        "故事缺少本场景必须登场的人物",
        "故事没有覆盖当天事件要求的人物。失败稿没有保存，也没有改动人物关系。",
    ),
    GenerationFailureCode.HIGH_CONFIDENCE_UNKNOWN_PERSON: (
        "故事角色一致性检查连续未通过",
        "故事引入了与当前人物关系不一致的角色。失败稿没有保存，也没有改动人物关系。",
    ),
    GenerationFailureCode.REPEATED_CONTENT: (
        "故事与已有内容过于重复",
        "多次生成仍与已经保存的故事高度重复。失败稿没有保存，你可以再次生成。",
    ),
    GenerationFailureCode.RETRY_EXHAUSTED: (
        "故事生成未能完成",
        "系统已经用完当前质量档位的自动尝试次数。失败稿没有保存，你可以再次生成。",
    ),
}


def _failure_code_from_exception(exc: BaseException) -> GenerationFailureCode:
    explicit = getattr(exc, "failure_code", None)
    if isinstance(explicit, GenerationFailureCode):
        return explicit

    findings = getattr(exc, "findings", ()) or ()
    hard_codes = {
        finding.code
        for finding in findings
        if isinstance(finding, ValidationFinding)
        and finding.severity is FindingSeverity.HARD
    }
    for code in (
        GenerationFailureCode.HIGH_CONFIDENCE_UNKNOWN_PERSON,
        GenerationFailureCode.REQUIRED_CAST_MISSING,
        GenerationFailureCode.INVALID_STORY_STRUCTURE,
        GenerationFailureCode.REPEATED_CONTENT,
    ):
        if code.value in hard_codes:
            return code

    message = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in message or "timed out" in message:
        return GenerationFailureCode.PROVIDER_TIMEOUT
    if "empty" in message or "no round event" in message:
        return GenerationFailureCode.EMPTY_OUTPUT
    if "shape" in message or "structure" in message or "option" in message:
        return GenerationFailureCode.INVALID_STORY_STRUCTURE
    if "introduced character" in message or "required cast" in message:
        return GenerationFailureCode.REQUIRED_CAST_MISSING
    if "unapproved" in message or "unknown person" in message:
        return GenerationFailureCode.HIGH_CONFIDENCE_UNKNOWN_PERSON
    if "repeat" in message or "duplicate" in message:
        return GenerationFailureCode.REPEATED_CONTENT
    return GenerationFailureCode.RETRY_EXHAUSTED


def build_generation_failure(
    exc: BaseException,
    *,
    quality_level: str,
    operation_id: str,
) -> GenerationFailure:
    code = _failure_code_from_exception(exc)
    summary, detail = _FAILURE_COPY[code]
    findings = getattr(exc, "findings", ()) or ()
    safe_messages = [
        finding.message.strip()
        for finding in findings
        if isinstance(finding, ValidationFinding)
        and finding.severity is FindingSeverity.HARD
        and finding.message.strip()
    ]
    if safe_messages:
        detail = f"{detail} 详情：{'；'.join(safe_messages[:3])[:360]}"
    return GenerationFailure(
        code=code,
        summary=summary,
        detail=detail,
        retryable=True,
        attempts_used=max(0, int(getattr(exc, "attempts_used", 0) or 0)),
        quality_level=str(quality_level or "expert"),
        operation_id=str(operation_id or ""),
    )
