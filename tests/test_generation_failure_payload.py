from src.ai.story_exceptions import (
    GenerationFailureCode,
    StoryGenerationFailure,
    build_generation_failure,
)
from src.ai.story_validation import FindingSeverity, ValidationFinding
from src.api.services.event_generation_operation import (
    EventGenerationKey,
    EventGenerationOperation,
)
from unittest.mock import MagicMock

import pytest

from src.ai.harness.quality_level import QualityLevel
from src.ai.quick_validator import QuickValidationResult
from src.ai.story_generator import StoryGenerator


def test_validation_failure_payload_is_friendly_and_retryable() -> None:
    finding = ValidationFinding(
        code="HIGH_CONFIDENCE_UNKNOWN_PERSON",
        severity=FindingSeverity.HARD,
        confidence=0.95,
        source="quick_validator",
        message="上一版故事出现名单外命名角色（马老板）",
        evidence="马老板决定下一步",
        repair_instruction="仅使用场景人物",
    )
    exc = StoryGenerationFailure(
        "internal validator stack detail",
        findings=[finding],
        attempts_used=3,
    )

    failure = build_generation_failure(
        exc,
        quality_level="expert",
        operation_id="operation-123",
    )

    assert failure.code is GenerationFailureCode.HIGH_CONFIDENCE_UNKNOWN_PERSON
    assert failure.summary == "故事角色一致性检查连续未通过"
    assert "马老板" in failure.detail
    assert "internal validator stack detail" not in failure.detail
    assert failure.retryable is True
    assert failure.attempts_used == 3
    assert failure.quality_level == "expert"
    assert failure.operation_id == "operation-123"


def test_timeout_payload_does_not_expose_raw_provider_message() -> None:
    failure = build_generation_failure(
        TimeoutError("secret-provider-route timed out"),
        quality_level="master",
        operation_id="operation-timeout",
    )

    assert failure.code is GenerationFailureCode.PROVIDER_TIMEOUT
    assert failure.summary == "模型服务响应超时"
    assert "secret-provider-route" not in failure.detail


def test_operation_snapshot_preserves_structured_failure() -> None:
    operation = EventGenerationOperation(
        EventGenerationKey(game_id=1, week=0, round_number=1)
    )
    failure = build_generation_failure(
        RuntimeError("provider unavailable"),
        quality_level="fast",
        operation_id=operation.operation_id,
    )

    operation.fail("故事生成失败", failure=failure.to_dict())
    snapshot = operation.snapshot_after(-1)

    assert snapshot.error == "故事生成失败"
    assert snapshot.failure == failure.to_dict()


def test_story_generator_preserves_last_hard_finding_and_attempt_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finding = ValidationFinding(
        code="HIGH_CONFIDENCE_UNKNOWN_PERSON",
        severity=FindingSeverity.HARD,
        confidence=0.95,
        source="quick_validator",
        message="上一版故事出现名单外命名角色（马老板）",
    )
    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: QuickValidationResult(
            passed=False,
            issues=[finding.message],
            findings=[finding],
        ),
    )
    client = MagicMock()
    client.call.return_value = "林岚在会议室核对项目安排，并等待陈越确认。" * 40
    generator = StoryGenerator(client, quality_level=QualityLevel.EXPERT)

    with pytest.raises(StoryGenerationFailure) as caught:
        generator.generate_round_event(
            player_state={"game_id": 1, "current_week": 1},
            language="zh",
            round_number=0,
            round_context="",
            option_generator=MagicMock(),
        )

    assert caught.value.findings == (finding,)
    assert caught.value.attempts_used == 2
    assert build_generation_failure(
        caught.value,
        quality_level="expert",
        operation_id="op",
    ).code is GenerationFailureCode.HIGH_CONFIDENCE_UNKNOWN_PERSON
