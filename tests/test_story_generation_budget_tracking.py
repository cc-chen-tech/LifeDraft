"""Provider-facing contracts for shared narrative call accounting."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from src.ai.budgets import (GenerationBudgetExceeded, GenerationCallTracker,
                            GenerationOperation, NarrativeKind,
                            resolve_narrative_budget)
from src.ai.client import AIClient
from src.ai.consistency_validator import ConsistencyValidator
from src.ai.option_generator import OptionGenerator
from src.ai.story_generator import StoryGenerator
from src.ai.story_rewriter import StoryRewriter
from src.ai.truncation_recovery import TruncationRecovery
from src.game.character_creation import CharacterCreator
from src.game.story_service import StoryService


class RecordingClient:
    def __init__(self, response: str = "完整故事。") -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []
        self.model = "test-model"

    def call(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self.response


def _tracker(*, quality: str = "expert") -> GenerationCallTracker:
    return GenerationCallTracker(
        resolve_narrative_budget(
            NarrativeKind.ROUND,
            GenerationOperation.GENERATE,
            quality,
            "zh",
        )
    )


def test_story_provider_call_consumes_prose_before_invocation() -> None:
    client = RecordingClient()
    generator = StoryGenerator(client, quality_level="expert")
    tracker = _tracker()

    for _ in range(2):
        generator._call_required_round_story(
            language="zh",
            generation_tracker=tracker,
            system_prompt="system",
            user_prompt="story",
            max_tokens=2048,
        )

    with pytest.raises(GenerationBudgetExceeded, match="prose"):
        generator._call_required_round_story(
            language="zh",
            generation_tracker=tracker,
            system_prompt="system",
            user_prompt="story",
            max_tokens=2048,
        )

    assert len(client.calls) == 2
    assert tracker.prose_calls == 2


def test_retry_wrapper_propagates_budget_exhaustion_without_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AIClient(api_key="test-key", model="test-model")
    tracker = _tracker(quality="fast")
    tracker.consume("prose")
    provider_call_count = 0

    def unexpected_call(**_kwargs: Any) -> str:
        nonlocal provider_call_count
        provider_call_count += 1
        return "unexpected"

    monkeypatch.setattr(client, "call", unexpected_call)

    with pytest.raises(GenerationBudgetExceeded):
        client.call_with_retry(
            system_prompt="system",
            user_prompt="story",
            retry_count=3,
            generation_tracker=tracker,
        )

    assert provider_call_count == 0


def test_option_provider_call_consumes_option_allowance_before_invocation() -> None:
    content = json.dumps(
        {
            "options": [
                {"text": "接受邀请", "effects": {"mood": 1}},
                {"text": "谨慎询问", "effects": {"knowledge": 1}},
                {"text": "暂时拒绝", "effects": {"energy": 1}},
            ]
        },
        ensure_ascii=False,
    )
    client = RecordingClient(content)
    generator = OptionGenerator(client)
    tracker = _tracker()

    for _ in range(2):
        generator.generate_options_only(
            story_description="他收到了一封邀请函。",
            player_state={},
            language="zh",
            generation_tracker=tracker,
        )

    fallback = generator.generate_options_only(
        story_description="他收到了一封邀请函。",
        player_state={},
        language="zh",
        generation_tracker=tracker,
    )

    assert len(client.calls) == 2
    assert tracker.option_calls == 2
    assert len(fallback.options) == 3


def test_consistency_provider_call_consumes_validation_and_uses_request_tokens() -> None:
    client = RecordingClient('{"issues": []}')
    validator = ConsistencyValidator(client)
    tracker = _tracker()
    world_model = SimpleNamespace(build_constraints_text=lambda _language: "facts")

    result = validator.validate_story(
        story_text="他按约定抵达车站。",
        world_model=world_model,
        player_state_dict={},
        character_settings={},
        language="zh",
        generation_tracker=tracker,
        max_output_tokens=tracker.budget.max_output_tokens,
    )
    second = validator.validate_story(
        story_text="他按约定抵达车站。",
        world_model=world_model,
        player_state_dict={},
        character_settings={},
        language="zh",
        generation_tracker=tracker,
        max_output_tokens=tracker.budget.max_output_tokens,
    )

    assert result.passed
    assert second.passed
    assert len(client.calls) == 1
    assert client.calls[0]["max_tokens"] == 2048
    assert tracker.validation_calls == 1


class RecordingStreamGenerator:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate_stream(self, **kwargs: Any):
        self.calls.append(kwargs)
        tracker = kwargs["generation_tracker"]
        tracker.consume("prose")
        return iter(["开场故事。"])


def test_opening_stream_uses_opening_budget_and_shared_tracker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "true")
    ai_generator = RecordingStreamGenerator()
    creator = CharacterCreator(ai_generator=ai_generator, language="zh")

    stream = creator.generate_opening_story(
        character_settings={"era": {"year": 2026}},
        player_name="林岚",
        life_vision="建立社区图书馆",
    )

    assert list(stream) == ["开场故事。"]
    assert len(ai_generator.calls) == 1
    call = ai_generator.calls[0]
    assert call["max_tokens"] == 1024
    assert "300-500字" in call["prompt"]
    assert "300-400字" not in call["prompt"]
    assert call["generation_tracker"].prose_calls == 1


class RecordingCompletionGenerator:
    quality_level = "expert"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate_completion(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        kwargs["generation_tracker"].consume("prose")
        return "林岚接受邀请后，与伙伴逐项核对合作条款，并约定明早继续讨论。"


def test_choice_continuation_uses_continuation_budget_and_shared_tracker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "true")
    ai_generator = RecordingCompletionGenerator()
    service = StoryService(ai_generator, language="zh")

    result = service.generate_story_continuation(
        event_description="伙伴递来一份合作协议。",
        chosen_option="先核对条款",
        effects={},
    )

    assert result.endswith("。")
    assert len(ai_generator.calls) == 1
    call = ai_generator.calls[0]
    assert call["max_tokens"] == 1536
    assert "400-700字" in call["prompt"]
    assert "500-800字" not in call["prompt"]
    assert call["generation_tracker"].prose_calls == 1


def test_full_output_rewrite_uses_original_length_band_and_request_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "true")
    original = "甲" * 99 + "。"
    rewritten = "乙" * 99 + "。"
    client = RecordingClient(rewritten)
    rewriter = StoryRewriter(client, quality_level="expert")
    monkeypatch.setattr(
        rewriter,
        "_quick_validate_and_retry_rewrite",
        lambda **kwargs: kwargs["rewritten_story"],
    )

    result = rewriter.rewrite_story_segment(
        full_story=original,
        segment_to_replace=original[10:20],
        user_instruction="改写语气",
        character_settings={},
        story_context="",
        language="zh",
    )

    assert result == rewritten
    assert len(client.calls) == 1
    assert client.calls[0]["max_tokens"] == 2048
    assert "故事应该80-120字" in client.calls[0]["user_prompt"]


def test_regeneration_uses_active_master_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "true")
    client = RecordingClient("林岚在会议室重新审视方案，并决定先核对风险。")
    rewriter = StoryRewriter(client, quality_level="master")
    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: SimpleNamespace(passed=True, issues=[]),
    )

    result = rewriter.regenerate_story(
        player_state={"week": 1, "relationships": {}},
        character_settings={},
        story_context="",
        language="zh",
    )

    assert result.endswith("。")
    assert len(client.calls) == 1
    assert client.calls[0]["max_tokens"] == 4096
    assert "1200-2200字" in client.calls[0]["user_prompt"]


def test_truncation_recovery_consumes_same_prose_allowance_and_stops_on_exhaustion() -> None:
    tracker = _tracker()
    tracker.consume("prose")  # originating generation call
    continuation_calls: list[dict[str, Any]] = []

    def continue_call(**kwargs: Any) -> str:
        continuation_calls.append(kwargs)
        return "继续写出尚未完成的部分"

    recovered = TruncationRecovery().recover(
        client_call=continue_call,
        system_prompt="system",
        original_prompt="story",
        partial_response="开头被截断",
        language="zh",
        generation_tracker=tracker,
    )

    assert recovered == "开头被截断继续写出尚未完成的部分"
    assert len(continuation_calls) == 1
    assert continuation_calls[0]["_allow_truncation_recovery"] is False
    assert tracker.prose_calls == 2
