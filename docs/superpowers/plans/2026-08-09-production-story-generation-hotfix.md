# Production Story Generation Hotfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DeepSeek V4 round-story requests spend their output budget on prose and guarantee that blank or CRITICAL-invalid stories never reach option generation as successful events.

**Architecture:** Add an opt-in `thinking` control at the `AIClient` request boundary, then centralize required round-story calls behind one StoryGenerator helper that disables DeepSeek thinking and rejects blank normalized text. Preserve the existing bounded retry and durable `StoryGenerationFailure` path, while preventing harness-invalid candidates from contaminating contextual fallback state.

**Tech Stack:** Python 3.11, OpenAI Python SDK (worktree venv currently 2.53.0; repository requirement `openai>=2.0.0`), httpx 0.27, pytest 9, Pydantic 2.

**Approved design:** [`docs/superpowers/specs/2026-08-09-production-story-generation-hotfix-design.md`](../specs/2026-08-09-production-story-generation-hotfix-design.md)

## Global constraints

- Work only in `/Users/luicy/story2/.worktrees/fix-production-story-generation-20260809` on `codex/fix-production-story-generation-20260809`.
- Follow red-green TDD: add the specified failing test first, run it, inspect the expected failure, then edit production code.
- `thinking=False` emits `{"thinking": {"type": "disabled"}}` only when the effective model name starts with `deepseek-v4` (case-insensitive). Omitted, `None`, `True`, and non-DeepSeek-V4 calls must retain their old payload shape.
- Propagate `thinking` through direct, streaming, model-fallback, and truncation-recovery paths.
- Apply `thinking=False` to all five round-prose call sites: initial draft, quick-consistency rewrite, shape rewrite, repeated-story rewrite, and AI-consistency rewrite.
- Preserve the exact inner failure messages `Story provider returned empty text` and `Story harness validation failed after final attempt` so the existing outer `StoryGenerationFailure` retains useful cause text.
- Do not add fake prose, generic options, a larger token budget, model or environment changes, frontend changes, NPC-age fixes, prompt-continuity changes, schema changes, credential changes, or deployment changes.
- Use the worktree's `venv/bin/python` (Python 3.11) for direct pytest commands.
- Known baseline: `tests/test_generate_round_event_retry.py` is already `4 failed, 1 passed` on `bca973c2` because it asserts removed fake-fallback behavior. Do not modify it, do not include it in a must-green set, and report it separately if rerun.
- Planning baseline rechecked before implementation: `tests/test_story_generation_failure_integrity.py` is `17 passed`; the adjacent AI/model/fallback/truncation set is `79 passed` under Python 3.11.15, openai 2.53.0, httpx 0.27.0, and pytest 9.1.1.

**Token-budget decision:** Production `finish_reason=length` proves that the 4096-token generation cap was reached. The simultaneous zero-character `content` under V4's default thinking mode most strongly supports—but does not directly prove without reasoning-token telemetry—the inference that reasoning consumed the available generation budget before prose began. Keep 4096 unchanged in this hotfix so the request-mode correction is isolated. Only open a follow-up budget change if non-thinking requests still reach `length` with otherwise valid prose.

---

## Task 1: Lock the AIClient request-shape contract with RED tests

**Files:**

- Create: `tests/test_ai_client_thinking_contract.py`
- Reference: `src/ai/client.py:91-334`
- Reference: `src/ai/truncation_recovery.py:70-105`

**Contract introduced by this task:**

```python
AIClient.call(
    self,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.8,
    max_tokens: int = 2000,
    stream_callback: Optional[Callable[[str], None]] = None,
    model: Optional[str] = None,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
    request_timeout: Optional[float] = None,
    thinking: Optional[bool] = None,
) -> str
```

- [ ] **Step 1: Add a real-SDK, fake-network contract test file**

Use the actual `openai.OpenAI` serializer and `AIClient.call()` implementation. Fake only the external HTTP boundary with `httpx.MockTransport`; do not replace `chat.completions.create` with a mock.

```python
"""Request-shape contracts for opt-in DeepSeek V4 thinking control."""

import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import openai
import pytest

from config.feature_flags import reset_features, set_feature
from src.ai.client import AIClient


STREAM_RESPONSE = (
    'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":0,'
    '"model":"deepseek-v4-flash","choices":[{"index":0,"delta":{"role":"assistant",'
    '"content":"story"},"finish_reason":null}]}\n\n'
    'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":0,'
    '"model":"deepseek-v4-flash","choices":[{"index":0,"delta":{},'
    '"finish_reason":"stop"}]}\n\n'
    'data: [DONE]\n\n'
)

STREAM_LENGTH_RESPONSE = (
    'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":0,'
    '"model":"deepseek-v4-flash","choices":[{"index":0,"delta":{"role":"assistant",'
    '"content":"partial "},"finish_reason":null}]}\n\n'
    'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":0,'
    '"model":"deepseek-v4-flash","choices":[{"index":0,"delta":{},'
    '"finish_reason":"length"}]}\n\n'
    'data: [DONE]\n\n'
)


@pytest.fixture(autouse=True)
def _reset_feature_flags() -> Iterator[None]:
    reset_features()
    yield
    reset_features()


def _completion_response(
    request: httpx.Request,
    body: dict[str, Any],
    *,
    content: str = "story",
    finish_reason: str = "stop",
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": body["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        },
        request=request,
    )


def _capture_transport(seen: list[dict[str, Any]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if body.get("stream"):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=STREAM_RESPONSE,
                request=request,
            )
        return _completion_response(request, body)

    return httpx.MockTransport(handler)


def _ai_client(model: str, http_client: httpx.Client) -> AIClient:
    client = object.__new__(AIClient)
    client.api_key = "test-key"
    client.model = model
    client.client = openai.OpenAI(
        api_key="test-key",
        base_url="https://provider.test/v1",
        http_client=http_client,
        max_retries=0,
    )
    return client


@pytest.mark.parametrize("model", ["deepseek-v4-flash", "DeepSeek-V4-Pro"])
@pytest.mark.parametrize("streaming", [False, True])
def test_deepseek_v4_false_serializes_disabled_thinking(
    model: str,
    streaming: bool,
) -> None:
    seen: list[dict[str, Any]] = []
    chunks: list[str] = []
    with httpx.Client(transport=_capture_transport(seen)) as http_client:
        client = _ai_client(model, http_client)
        callback: Callable[[str], None] | None = chunks.append if streaming else None
        result = client.call(
            "system",
            "user",
            max_tokens=4096,
            stream_callback=callback,
            thinking=False,
        )

    assert result == "story"
    assert len(seen) == 1
    assert seen[0]["max_tokens"] == 4096
    assert seen[0]["thinking"] == {"type": "disabled"}
    if streaming:
        assert chunks == ["story"]


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("thinking_kwargs", [{}, {"thinking": None}, {"thinking": True}])
def test_non_false_thinking_preserves_deepseek_payload(
    thinking_kwargs: dict[str, bool | None],
    streaming: bool,
) -> None:
    seen: list[dict[str, Any]] = []
    chunks: list[str] = []
    with httpx.Client(transport=_capture_transport(seen)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        callback: Callable[[str], None] | None = chunks.append if streaming else None
        assert client.call(
            "system",
            "user",
            stream_callback=callback,
            **thinking_kwargs,
        ) == "story"

    assert "thinking" not in seen[0]
    if streaming:
        assert chunks == ["story"]


def test_non_deepseek_ignores_false_thinking() -> None:
    seen: list[dict[str, Any]] = []
    with httpx.Client(transport=_capture_transport(seen)) as http_client:
        client = _ai_client("gpt-4o-mini", http_client)
        assert client.call("system", "user", thinking=False) == "story"

    assert "thinking" not in seen[0]


def test_model_fallback_preserves_disabled_thinking_for_each_deepseek_model() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if len(seen) <= 2:
            return httpx.Response(
                503,
                json={
                    "error": {
                        "message": "temporary provider failure",
                        "type": "server_error",
                        "code": "server_error",
                    }
                },
                request=request,
            )
        return _completion_response(request, body)

    set_feature("model_fallback", True)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        assert client.call("system", "user", thinking=False) == "story"

    assert [body["model"] for body in seen] == [
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "gpt-4o-mini",
    ]
    assert all(body["thinking"] == {"type": "disabled"} for body in seen[:2])
    assert "thinking" not in seen[2]


def test_truncation_recovery_preserves_disabled_thinking() -> None:
    seen: list[dict[str, Any]] = []
    completions = iter(
        [
            ("partial ", "length"),
            ("ending.", "stop"),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        content, finish_reason = next(completions)
        return _completion_response(
            request,
            body,
            content=content,
            finish_reason=finish_reason,
        )

    set_feature("truncation_recovery", True)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        result = client.call("system", "user", thinking=False)

    assert result == "partial ending."
    assert len(seen) == 2
    assert all(body["thinking"] == {"type": "disabled"} for body in seen)


def test_streaming_truncation_recovery_preserves_disabled_thinking() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if body.get("stream"):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=STREAM_LENGTH_RESPONSE,
                request=request,
            )
        return _completion_response(request, body, content="ending.")

    chunks: list[str] = []
    set_feature("truncation_recovery", True)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        result = client.call(
            "system",
            "user",
            stream_callback=chunks.append,
            thinking=False,
        )

    assert result == "partial ending."
    assert chunks == ["partial "]
    assert len(seen) == 2
    assert seen[0]["stream"] is True
    assert "stream" not in seen[1]
    assert all(body["thinking"] == {"type": "disabled"} for body in seen)
```

The assertions inspect only the provider-specific fields and model sequence. They avoid coupling the tests to unrelated OpenAI SDK defaults while still failing if thinking control is absent, malformed, or applied to a non-DeepSeek fallback.

- [ ] **Step 2: Run the new test file and record RED**

Run:

```bash
venv/bin/python -m pytest tests/test_ai_client_thinking_contract.py -q
```

Expected before implementation: the cases that pass `thinking` fail before transport with `TypeError: AIClient.call() got an unexpected keyword argument 'thinking'`; the omitted-control characterization case passes. Confirm that the traceback stops during `AIClient.call` keyword binding before the transport handler can run.

- [ ] **Step 3: Commit only the RED test**

```bash
git add tests/test_ai_client_thinking_contract.py
git commit -m "test: define DeepSeek thinking request contract"
```

---

## Task 2: Implement the per-call DeepSeek thinking control

**Files:**

- Modify: `src/ai/client.py:37-334`
- Test: `tests/test_ai_client_thinking_contract.py`
- No change: `src/ai/truncation_recovery.py`
- No change: `src/ai/model_fallback.py`

- [ ] **Step 1: Add one provider-shape helper**

Place this immediately after `_is_max_tokens_error`:

```python
def _thinking_request_params(
    model: str,
    thinking: Optional[bool],
) -> Dict[str, Any]:
    """Return provider-specific request fields for explicit DeepSeek V4 control."""
    if thinking is not False or not model.lower().startswith("deepseek-v4"):
        return {}
    return {"extra_body": {"thinking": {"type": "disabled"}}}
```

Do not serialize `thinking=True`; the approved contract is opt-in disabling only.

- [ ] **Step 2: Thread the optional argument through all internal call paths**

Append `thinking: Optional[bool] = None` to `AIClient.call`, `AIClient._call_with_model_fallback`, and `AIClient._call_impl`. Document it in the public `AIClient.call` Args section. Pass `thinking=thinking` in both branches of `call()` and in every `_call_impl()` invocation inside `_call_with_model_fallback()`.

Add this line after the existing penalty/timeout fields are assembled in both streaming and synchronous branches:

```python
extra_params.update(_thinking_request_params(use_model, thinking))
```

and:

```python
extra_params_sync.update(_thinking_request_params(use_model, thinking))
```

The effective `use_model` must be used so a fallback from `deepseek-v4-pro` to `gpt-4o-mini` automatically stops emitting provider-specific fields.

- [ ] **Step 3: Preserve the control in truncation continuations**

Add `thinking=thinking` to the streaming and synchronous `TruncationRecovery.recover` calls in `_call_impl`. `TruncationRecovery.recover` already accepts `**call_kwargs` and forwards them to `client_call`, so its signature and file remain unchanged.

- [ ] **Step 4: Run focused GREEN and adjacent AI contracts**

```bash
venv/bin/python -m pytest tests/test_ai_client_thinking_contract.py -q
venv/bin/python -m pytest \
  tests/test_ai_modules.py \
  tests/test_deepseek_v4_model_contract.py \
  tests/test_model_fallback_contract.py \
  tests/test_truncation_recovery_contract.py \
  -q
```

Expected: both commands pass. Inspect one captured body while debugging if needed, but do not print API keys or authorization headers.

- [ ] **Step 5: Review the Task 2 diff and commit**

```bash
git diff --check
git diff -- src/ai/client.py tests/test_ai_client_thinking_contract.py
git add src/ai/client.py
git commit -m "fix: control DeepSeek thinking per request"
```

---

## Task 3: Lock StoryGenerator failure integrity and all five call sites with RED tests

**Files:**

- Modify: `tests/test_story_generation_failure_integrity.py:1-410`
- Modify: `tests/test_story_generator_best_story_db.py:1-170`
- Reference: `src/ai/story_generator.py:587-983`
- Reference: `src/ai/story_generator.py:1119-1235`

- [ ] **Step 1: Add focused imports and deterministic fakes**

Add these imports with the existing top-level imports:

```python
from src.ai.consistency_validator import (
    ConsistencyIssue,
    ValidationResult as ConsistencyValidationResult,
)
from src.ai.harness import ConstraintCheckResult, ValidationResult
from src.ai.harness.quality_level import QualityLevel
from src.ai.models import EventOption, GameEvent
```

Add these fakes after `InvalidEffectsStoryGenerator`:

```python
class StaticStoryClient:
    def __init__(self, story: str):
        self.story = story
        self.calls: list[dict[str, object]] = []

    def call(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return self.story


class SequenceStoryClient:
    def __init__(self, stories: list[str]):
        self.stories = iter(stories)
        self.calls: list[dict[str, object]] = []

    def call(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return next(self.stories)


class RecordingOptionGenerator:
    def __init__(self):
        self.story_descriptions: list[str] = []

    def generate_options_only(self, **kwargs: object) -> GameEvent:
        story = str(kwargs["story_description"])
        self.story_descriptions.append(story)
        return GameEvent(
            event_description=story,
            options=[
                EventOption(text="继续核对", effects={}),
                EventOption(text="暂缓处理", effects={}),
            ],
        )

    def validate_and_fix_relationships(self, *_args: object, **_kwargs: object) -> None:
        return None

    def validate_options_consistency(
        self,
        *_args: object,
        **_kwargs: object,
    ) -> list[str]:
        return []


class AlwaysCriticalPipeline:
    def __init__(self):
        self.calls = 0

    def validate(self, **_kwargs: object) -> ValidationResult:
        self.calls += 1
        return ValidationResult(
            passed=False,
            score=55.0,
            critical_failures=[
                ConstraintCheckResult(
                    constraint_type="decision_point_ending",
                    priority="CRITICAL",
                    passed=False,
                    evidence="terminal critical fixture",
                )
            ],
            total_checked=1,
            total_passed=0,
        )
```

- [ ] **Step 2: Add the production blank-output reproduction**

Place this immediately after `test_round_story_generation_surfaces_provider_failure`:

```python
def test_round_generation_rejects_blank_provider_text_before_option_generation(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    client = StaticStoryClient("  \n\t")
    option_generator = RecordingOptionGenerator()

    with pytest.raises(StoryGenerationFailure, match="Story provider returned empty text"):
        StoryGenerator(client, quality_level=QualityLevel.EXPERT).generate_round_event(
            player_state={"week": 0, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            character_settings={},
            option_generator=option_generator,
        )

    assert len(client.calls) == 3
    assert all(call["thinking"] is False for call in client.calls)
    assert option_generator.story_descriptions == []
```

This reproduces the production shape: three Expert attempts, zero normalized story characters, and an option generator that would otherwise return a structurally valid event.

- [ ] **Step 3: Add the terminal CRITICAL reproduction**

```python
def test_round_generation_rejects_final_critical_candidate_before_option_generation(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: SimpleNamespace(passed=True, warnings=[], issues=[]),
    )
    monkeypatch.setattr(
        "src.ai.story_generator.validate_narrative_quality",
        lambda *_args, **_kwargs: [],
    )
    story = "林岚和陈越在影院办公室核对预算，逐项确认施工日期，并决定是否先联系周师傅复核报价。" * 22
    client = StaticStoryClient(story)
    pipeline = AlwaysCriticalPipeline()
    option_generator = RecordingOptionGenerator()
    generator = StoryGenerator(client, quality_level=QualityLevel.EXPERT)
    generator._validation_pipeline = pipeline

    with pytest.raises(
        StoryGenerationFailure,
        match="Story harness validation failed after final attempt",
    ):
        generator.generate_round_event(
            player_state={"week": 0, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            character_settings={},
            option_generator=option_generator,
        )

    assert len(client.calls) == 3
    assert pipeline.calls == 3
    assert option_generator.story_descriptions == []
```

This test must still fail if an implementation merely raises on the final harness result but leaves the invalid candidate in `best_valid_story_text`; the existing outer fallback would otherwise turn it back into a successful `GameEvent`.

- [ ] **Step 4: Add quick- and AI-consistency rewrite contracts**

```python
def test_round_generation_disables_thinking_for_quick_consistency_rewrite(
    monkeypatch,
) -> None:
    initial_story = "林岚和陈越在影院办公室核对预算，并暂时搁置了施工报价。" * 20
    repaired_story = "林岚和陈越重新核对预算，并确认本周先请周师傅复核施工报价。" * 20
    client = SequenceStoryClient([initial_story, repaired_story])
    option_generator = RecordingOptionGenerator()
    quick_results = iter(
        [
            SimpleNamespace(passed=False, warnings=[], issues=["forced quick retry"]),
            SimpleNamespace(passed=True, warnings=[], issues=[]),
        ]
    )
    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: next(quick_results),
    )
    monkeypatch.setattr(
        "src.ai.story_generator.validate_narrative_quality",
        lambda *_args, **_kwargs: [],
    )

    StoryGenerator(client).generate_round_event(
        player_state={"week": 0, "current_round": 0},
        language="zh",
        round_number=0,
        round_context="",
        option_generator=option_generator,
    )

    assert len(client.calls) == 2
    assert all(call["thinking"] is False for call in client.calls)
    assert option_generator.story_descriptions == [repaired_story]


def test_round_generation_rejects_blank_ai_consistency_rewrite(
    monkeypatch,
) -> None:
    story = "林岚和陈越在影院办公室核对预算，并确认本周先请周师傅复核施工报价。" * 20
    client = SequenceStoryClient([story, "  \n\t"])
    option_generator = RecordingOptionGenerator()
    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: SimpleNamespace(passed=True, warnings=[], issues=[]),
    )
    monkeypatch.setattr(
        "src.ai.story_generator.validate_narrative_quality",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "src.ai.consistency_validator.ConsistencyValidator.validate_story",
        lambda *_args, **_kwargs: ConsistencyValidationResult(
            passed=False,
            issues=[
                ConsistencyIssue(
                    dimension="causal",
                    severity="CRITICAL",
                    description="forced critical rewrite",
                    fix_suggestion="rewrite the scene",
                )
            ],
            fix_instructions="\nRewrite the scene.",
        ),
    )

    with pytest.raises(StoryGenerationFailure, match="Story provider returned empty text"):
        StoryGenerator(client).generate_round_event(
            player_state={"week": 0, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            option_generator=option_generator,
            world_model=object(),
        )

    assert len(client.calls) == 2
    assert all(call["thinking"] is False for call in client.calls)
    assert option_generator.story_descriptions == []
```

- [ ] **Step 5: Extend the existing shape and repeat tests to cover the remaining call sites**

After the existing `client.call.call_count` assertion in each named test, add:

```python
assert all(call.kwargs["thinking"] is False for call in client.call.call_args_list)
```

Apply it to:

- `test_round_generation_retries_when_provider_repeats_committed_story` — covers initial draft plus repeated-story rewrite.
- `test_round_generation_rejects_an_overlong_story_after_shape_retry` — covers initial draft plus shape rewrite.

Together with Steps 2 and 4, these assertions exercise all five approved round-prose call sites at runtime.

- [ ] **Step 6: Update best-story fixtures so only Harness-accepted prose can be a fallback**

The new per-attempt snapshot intentionally invalidates two old fixtures in `tests/test_story_generator_best_story_db.py`: they currently treat `passed=False` CRITICAL stories as valid best-story fallback. Preserve the legitimate fallback contract by rewriting those fixtures around accepted stories.

For `test_best_story_text_used_when_final_is_short`:

- construct the generator with `QualityLevel.EXPERT`;
- reduce the repeated base story from `* 10` to `* 6` so it is within the Expert 800-1200 character shape budget;
- set `client.call.side_effect = [long_story, short_story, ""]`;
- set pipeline results to `passed=True` for the long story, then `passed=False` with one CRITICAL failure for the short story;
- set retry-controller results to `(False, None)`, then `(True, "fix it")`;
- keep option generation failing, so the first accepted long story survives the later CRITICAL and blank attempts and becomes contextual fallback.

Use concrete side effects of this form:

```python
client.call.side_effect = [long_story, short_story, ""]
gen._validation_pipeline.validate.side_effect = [
    MagicMock(
        passed=True,
        score=95,
        critical_failures=[],
        detailed_checks={},
    ),
    MagicMock(
        passed=False,
        score=50,
        critical_failures=["test"],
        detailed_checks={},
    ),
]
gen._retry_controller.should_retry.side_effect = [
    (False, None),
    (True, "fix it"),
]
```

For `test_best_story_tracks_longest_across_attempts`:

- use `QualityLevel.EXPERT`;
- reduce `medium_story` from base `* 10` to base `* 6`, leaving the two extra sentences on `long_story`; both candidates then fit the Expert shape budget;
- set `client.call.side_effect = [medium_story, long_story, ""]`;
- make both nonblank pipeline results `passed=True` and both retry-controller results `(False, None)`;
- keep option generation failing so both accepted candidates are considered and the longest one survives the final blank attempt.

```python
client.call.side_effect = [medium_story, long_story, ""]
gen._validation_pipeline.validate.side_effect = [
    MagicMock(
        passed=True,
        score=95,
        critical_failures=[],
        detailed_checks={},
    ),
    MagicMock(
        passed=True,
        score=95,
        critical_failures=[],
        detailed_checks={},
    ),
]
gen._retry_controller.should_retry.side_effect = [
    (False, None),
    (False, None),
]
```

Update the module/test comments to say that fallback uses the longest Harness-accepted story after later failures; do not retain wording that endorses CRITICAL-invalid fallback.

- [ ] **Step 7: Run the focused nodes and record RED**

```bash
venv/bin/python -m pytest \
  tests/test_story_generation_failure_integrity.py::test_round_generation_rejects_blank_provider_text_before_option_generation \
  tests/test_story_generation_failure_integrity.py::test_round_generation_rejects_final_critical_candidate_before_option_generation \
  tests/test_story_generation_failure_integrity.py::test_round_generation_disables_thinking_for_quick_consistency_rewrite \
  tests/test_story_generation_failure_integrity.py::test_round_generation_rejects_blank_ai_consistency_rewrite \
  tests/test_story_generation_failure_integrity.py::test_round_generation_retries_when_provider_repeats_committed_story \
  tests/test_story_generation_failure_integrity.py::test_round_generation_rejects_an_overlong_story_after_shape_retry \
  -q

venv/bin/python -m pytest tests/test_story_generator_best_story_db.py -q
```

Expected before implementation:

- blank-output and final-CRITICAL tests report `DID NOT RAISE` or fail their exact-message assertion because current code reaches options/contextual fallback;
- call-site assertions fail with missing `thinking` keys;
- the consistency blank rewrite is swallowed and returns the original story instead of failing.
- the rewritten best-story characterization file remains green before implementation and proves accepted fallback is still required.

- [ ] **Step 8: Commit the RED tests and accepted-fallback characterizations**

```bash
git add \
  tests/test_story_generation_failure_integrity.py \
  tests/test_story_generator_best_story_db.py
git commit -m "test: reproduce invalid round story completion"
```

---

## Task 4: Enforce required round prose before option generation

**Files:**

- Modify: `src/ai/story_generator.py:31-983`
- Modify: `src/ai/story_generator.py:1119-1235`
- Test: `tests/test_story_generation_failure_integrity.py`
- Test: `tests/test_story_generator_best_story_db.py`

**Private interface introduced by this task:**

```python
StoryGenerator._call_required_round_story(
    *,
    language: str,
    **call_kwargs: Any,
) -> str
```

- [ ] **Step 1: Add a private, distinguishable blank-output error and one call helper**

Add near the module logger:

```python
class _EmptyStoryProviderOutput(ValueError):
    """A round-prose provider call returned no normalized text."""
```

Add to `StoryGenerator` after `_story_request_timeout_seconds`:

```python
def _call_required_round_story(
    self,
    *,
    language: str,
    **call_kwargs: Any,
) -> str:
    """Generate required round prose in non-thinking mode and reject blanks."""
    provider_story = self.client.call(thinking=False, **call_kwargs)
    story_text = normalize_generated_story(
        provider_story or "",
        language=language,
    )
    if not story_text.strip():
        raise _EmptyStoryProviderOutput("Story provider returned empty text")
    return story_text
```

The private subclass lets `_validate_and_retry_story` re-raise only this integrity failure while retaining its existing soft handling for unrelated consistency-validator failures.

- [ ] **Step 2: Route all five prose calls through the helper**

Replace each direct `self.client.call` plus its following normalization in:

1. initial round draft;
2. quick-consistency rewrite;
3. shape rewrite;
4. repeated-story rewrite;
5. AI-consistency rewrite.

Each call becomes this shape, retaining its existing prompts, temperatures, token limits, callbacks, penalties, and timeout:

```python
story_text = self._call_required_round_story(
    language=language,
    system_prompt=sys_prompt,
    user_prompt=attempt_prompt,
    temperature=current_temp,
    max_tokens=generation_budget.max_tokens,
    stream_callback=stream_callback if attempt == 0 else None,
    frequency_penalty=0.4,
    presence_penalty=0.4,
    request_timeout=self._story_request_timeout_seconds(),
)
```

The initial draft, quick-consistency rewrite, shape rewrite, and repeated-story rewrite must assign the helper result directly to `story_text`. The AI-consistency method may keep its local `retry_story` name before returning it. Remove the four now-redundant outer `normalize_generated_story` statements. Do not route option generation, consistency judging, or any non-round feature through this helper.

Use these assignment shapes so a rewrite cannot leave the old draft in `story_text`:

```python
story_text = self._call_required_round_story(
    language=language,
    system_prompt=sys_prompt,
    user_prompt=retry_prompt,
    temperature=0.65,
    max_tokens=generation_budget.max_tokens,
    stream_callback=stream_callback if attempt == 0 else None,
    frequency_penalty=0.4,
    presence_penalty=0.4,
    request_timeout=self._story_request_timeout_seconds(),
)
```

and inside `_validate_and_retry_story`:

```python
retry_story = self._call_required_round_story(
    language=language,
    system_prompt=sys_prompt,
    user_prompt=retry_prompt,
    temperature=0.7,
    max_tokens=8192,
    stream_callback=stream_callback,
    frequency_penalty=0.3,
    presence_penalty=0.3,
    request_timeout=self._story_request_timeout_seconds(),
)
```

- [ ] **Step 3: Let a blank AI-consistency rewrite reach the outer bounded failure path**

In `_validate_and_retry_story`, add this exception branch immediately before its broad `except Exception`:

```python
except _EmptyStoryProviderOutput:
    raise
```

Do not re-raise other consistency-validator exceptions in this hotfix.

- [ ] **Step 4: Protect best-story fallback state per attempt**

At the start of every outer attempt, before provider work, snapshot the last previously accepted fallback candidate:

```python
for attempt in range(max_attempts):
    best_story_before_attempt = best_valid_story_text
    story_text = None
```

Add a dedicated outer exception branch before the existing `(ValueError, ValidationError, json.JSONDecodeError)` branch:

```python
except _EmptyStoryProviderOutput as e:
    best_valid_story_text = best_story_before_attempt
    logger.warning(f"Round event attempt {attempt + 1} failed: {e}")
    last_generation_error = e
```

This prevents a valid-shaped but consistency-invalid draft from being resurrected after its rewrite returns blank, while preserving a candidate accepted during an earlier attempt.

- [ ] **Step 5: Reject an exhausted CRITICAL harness result and restore the snapshot**

Immediately after `validation_result` is produced, restore fallback state for any CRITICAL-invalid candidate:

```python
if not validation_result.passed:
    best_valid_story_text = best_story_before_attempt
```

Keep the existing `RetryController.should_retry` call. After its existing `if should_retry` status/logging/`continue` block, add:

```python
if (
    not validation_result.passed
    and self._quality_profile.enforce_validation_on_all_attempts
):
    raise ValueError("Story harness validation failed after final attempt")
```

This ordering preserves existing retries, allows warning-only candidates (`validation_result.passed is True`) to continue under Expert policy, and prevents an exhausted CRITICAL candidate from reaching options or contextual fallback.

- [ ] **Step 6: Audit the five sites before running tests**

```bash
rg -n "self\.client\.call\(|_call_required_round_story\(" src/ai/story_generator.py
```

Expected round-story result: the five prose-generation/rewrite sites use `_call_required_round_story`; direct `self.client.call` occurrences that belong to other public story APIs or validation helpers remain unchanged unless they are one of the five approved sites.

- [ ] **Step 7: Run focused GREEN and affected story regressions**

```bash
venv/bin/python -m pytest \
  tests/test_story_generation_failure_integrity.py::test_round_generation_rejects_blank_provider_text_before_option_generation \
  tests/test_story_generation_failure_integrity.py::test_round_generation_rejects_final_critical_candidate_before_option_generation \
  tests/test_story_generation_failure_integrity.py::test_round_generation_disables_thinking_for_quick_consistency_rewrite \
  tests/test_story_generation_failure_integrity.py::test_round_generation_rejects_blank_ai_consistency_rewrite \
  tests/test_story_generation_failure_integrity.py::test_round_generation_retries_when_provider_repeats_committed_story \
  tests/test_story_generation_failure_integrity.py::test_round_generation_rejects_an_overlong_story_after_shape_retry \
  -q

venv/bin/python -m pytest \
  tests/test_story_generation_failure_integrity.py \
  tests/test_story_generator_best_story_db.py \
  tests/test_story_generator_quality_level.py \
  tests/test_harness_retry_loop.py \
  tests/test_gate_gameplay_behavior_no_mock.py \
  -q
```

Expected: both commands pass. If an older fallback assertion fails, first determine whether it belongs to the documented stale `tests/test_generate_round_event_retry.py`; do not broaden this branch to restore fake prose.

- [ ] **Step 8: Review the Task 4 diff and commit**

```bash
git diff --check
git diff -- src/ai/story_generator.py tests/test_story_generation_failure_integrity.py
git add src/ai/story_generator.py
git commit -m "fix: reject invalid round stories before options"
```

---

## Task 5: Verify the integrated hotfix without touching production

**Files:**

- Verify: `src/ai/client.py`
- Verify: `src/ai/story_generator.py`
- Verify: `tests/test_ai_client_thinking_contract.py`
- Verify: `tests/test_story_generation_failure_integrity.py`
- Verify: `tests/test_story_generator_best_story_db.py`
- Do not modify production, deployment files, `.env`, or database state.

- [ ] **Step 1: Run all hotfix and adjacent backend contracts from a fresh process**

```bash
venv/bin/python -m pytest \
  tests/test_ai_client_thinking_contract.py \
  tests/test_ai_modules.py \
  tests/test_deepseek_v4_model_contract.py \
  tests/test_model_fallback_contract.py \
  tests/test_truncation_recovery_contract.py \
  tests/test_story_generation_failure_integrity.py \
  tests/test_story_generator_best_story_db.py \
  tests/test_story_generator_quality_level.py \
  tests/test_harness_retry_loop.py \
  tests/test_gate_gameplay_behavior_no_mock.py \
  -q
```

Expected: green. Record the exact passed count and wall time.

- [ ] **Step 2: Run repository quality gates separately**

```bash
./test.sh preflight
./test.sh all
```

Expected: report preflight and the layered `all` result separately. `./test.sh all` owns the integration worktree's isolated database, ports, backend, frontend build, and Playwright runtime. Do not substitute a green frontend suite or one green component for the full layered result.

- [ ] **Step 3: Compare the documented stale baseline without fixing it**

```bash
venv/bin/python -m pytest tests/test_generate_round_event_retry.py -q
```

Expected baseline comparison: exactly `4 failed, 1 passed`, matching pre-change `bca973c2`. If the count changes, inspect it as a regression signal; do not edit this stale test in the hotfix.

- [ ] **Step 4: Exercise a local create-to-first-round smoke path**

Use only the isolated local E2E database/runtime created by the test harness. Do not connect the branch to `/opt/story2`, the production database, or production containers.

First run the managed E2E layer:

```bash
./test.sh e2e
```

If a local provider credential is available to the worktree, additionally run the existing AI-heavy full-game flow against a fresh isolated runtime and verify that the first round displays non-empty story text and at least two options. Record only sanitized outcome data: effective model when observable, story character count, option count, and whether the existing backend log emitted a `finish_reason=length` truncation warning. The current client does not log successful `finish_reason=stop`, so record it as `not exposed` rather than inferring it from silence. A visible `length` result after non-thinking mode is enabled is a follow-up token-budget signal, not permission to expand this hotfix. If no non-production provider credential is available, mark this live-provider smoke as `SKIPPED (credential unavailable)` rather than borrowing production credentials or claiming it passed. The deterministic request test already proves that `thinking=disabled` and `max_tokens=4096` coexist in the serialized body; all deterministic unit and contract gates remain mandatory.

- [ ] **Step 5: Perform final scope and secret audit**

```bash
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
git diff --name-only origin/main...HEAD
git status --short --branch
git diff origin/main...HEAD -- src tests | \
  rg -n "BEGIN (RSA |OPENSSH )?PRIVATE KEY|sshpass -p|Authorization: Bearer|root@"
```

Expected changed implementation/test files only:

```text
docs/superpowers/specs/2026-08-09-production-story-generation-hotfix-design.md
docs/superpowers/plans/2026-08-09-production-story-generation-hotfix.md
src/ai/client.py
src/ai/story_generator.py
tests/test_ai_client_thinking_contract.py
tests/test_story_generation_failure_integrity.py
tests/test_story_generator_best_story_db.py
```

The secret audit must produce no credential or remote-login matches. The literal provider endpoint, password, RSA key contents, remote logs, game prose, and production database records must not enter the branch.

- [ ] **Step 6: Request code review before any publish decision**

Use `superpowers:requesting-code-review` on the final diff. Address only defects within the approved hotfix scope. Do not push, open a PR, merge, deploy, or mutate production unless the user separately authorizes that action.

## Completion evidence checklist

- [ ] AIClient request tests were observed RED, then GREEN.
- [ ] Blank-provider and terminal-CRITICAL tests were observed RED, then GREEN.
- [ ] All five round-prose call sites have runtime coverage for `thinking=False`.
- [ ] Blank normalized text cannot reach quick validation, harness, consistency validation, or options.
- [ ] CRITICAL-invalid candidates cannot enter options or be revived by contextual fallback.
- [ ] Omitted/non-DeepSeek AI calls retain their old request payload.
- [ ] Truncation recovery and model fallback retain the per-call control.
- [ ] Preflight and layered `./test.sh all` results are reported independently.
- [ ] The known stale retry test baseline is reported honestly and not folded into a green claim.
- [ ] No production, deployment, credential, frontend, NPC-age, or prompt-continuity changes are present.
