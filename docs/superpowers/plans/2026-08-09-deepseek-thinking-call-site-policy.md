# DeepSeek Thinking Call-Site Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explicitly disable DeepSeek V4 thinking for five high-risk story/JSON paths, complete wrapper propagation, and reject empty or malformed consistency-validator output.

**Architecture:** Keep `AIClient.call` as the single effective-model request boundary introduced by PR #265. Extend wrapper signatures with an optional `thinking` value, reuse the existing provider-specific request-kwargs helper for the raw-stream facade, and make policy explicit at each selected call site. Consistency parsing returns a deterministic CRITICAL result for non-dict output while preserving valid JSON and transport-availability behavior.

**Tech Stack:** Python 3.11, OpenAI Python SDK 2.53.0, httpx MockTransport, pytest 9, existing Story2 AI facade/services.

## Global Constraints

- The branch is stacked on PR #265 commit `55ff957a`; do not duplicate or remove its request-level thinking implementation.
- No global `thinking=False` default.
- No `max_tokens`, prompt-content, schema, API route, frontend, provider credential, or deployment changes.
- Omitted/`None`/`True` and non-DeepSeek-V4 effective models retain their previous request shape.
- Provider/transport exceptions in consistency validation retain the existing availability-first pass-through behavior.
- Every production change must be preceded by a focused failing test and an observed expected RED result.

---

### Task 1: Complete thinking propagation interfaces

**Files:**
- Modify: `tests/test_ai_client_thinking_contract.py`
- Modify: `src/ai/client.py:464-572`
- Modify: `src/ai/generator.py:68-177`

**Interfaces:**
- Produces: `AIClient.call_json(..., thinking: Optional[bool] = None)`
- Produces: `AIClient.call_with_retry(..., thinking: Optional[bool] = None)`
- Produces: `EventGenerator.generate_completion(..., thinking: Optional[bool] = None)`
- Produces: `EventGenerator.generate_completion_json(..., thinking: Optional[bool] = None)`
- Produces: `EventGenerator.generate_stream(..., thinking: Optional[bool] = None)`

- [ ] **Step 1: Add real request-shape RED tests**

Extend `tests/test_ai_client_thinking_contract.py` using the existing real OpenAI SDK and `httpx.MockTransport` helpers:

```python
from src.ai.generator import EventGenerator

def test_call_json_preserves_disabled_thinking() -> None:
    seen = []
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return _completion_response(request, body, content='{"value": 1}')
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        assert client.call_json("system", "user", thinking=False) == {"value": 1}
    assert seen[0]["thinking"] == {"type": "disabled"}

def test_call_with_retry_preserves_disabled_thinking_on_every_attempt() -> None:
    seen = []
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if len(seen) == 1:
            return httpx.Response(503, json={"error": {"message": "retry"}}, request=request)
        return _completion_response(request, body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        assert client.call_with_retry("system", "user", retry_count=2, thinking=False) == "story"
    assert [body["thinking"] for body in seen] == [
        {"type": "disabled"}, {"type": "disabled"}
    ]

def test_raw_generate_stream_serializes_disabled_thinking() -> None:
    seen = []
    with httpx.Client(transport=_capture_transport(seen)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        generator = object.__new__(EventGenerator)
        generator.ai_client = client
        chunks = list(generator.generate_stream("user", "system", thinking=False))
    assert len(chunks) == 2
    assert seen[0]["thinking"] == {"type": "disabled"}
```

Make the JSON transport response return `{"value": 1}` for the JSON test and assert the parsed literal. Also add controls proving omitted thinking on raw stream does not add a `thinking` field and a non-V4 raw stream ignores `False`.

Before writing each body, name the mutation it catches: wrapper omission, retry-attempt omission, raw-stream bypass, or global payload pollution.

- [ ] **Step 2: Run the focused tests and verify expected RED**

Run:

```bash
../fix-production-story-generation-20260809/venv/bin/python -m pytest \
  tests/test_ai_client_thinking_contract.py -q
```

Expected: existing 15 tests pass; new tests fail with unexpected `thinking` keyword on `call_json`, `call_with_retry`, or `generate_stream`. No failure may be caused by fixture or transport setup.

- [ ] **Step 3: Implement minimal wrapper propagation**

In `src/ai/client.py`, add a trailing `thinking: Optional[bool] = None` to `call_json` and `call_with_retry`, then pass it unchanged into every `self.call(...)` invocation.

In `src/ai/generator.py`, import `_thinking_request_params` with `AIClient`, add the same trailing parameter to `_call_ai`, `generate_completion`, `generate_completion_json`, and `generate_stream`, and forward it. The raw stream method must assign `request_params = _thinking_request_params(use_model, thinking)` and expand `**request_params` in the existing `client.chat.completions.create` call alongside its unchanged model, messages, temperature, `max_tokens`, and `stream=True` arguments.

- [ ] **Step 4: Run focused and adjacent GREEN tests**

Run:

```bash
../fix-production-story-generation-20260809/venv/bin/python -m pytest \
  tests/test_ai_client_thinking_contract.py \
  tests/test_ai_client_usage.py \
  tests/test_ai_modules.py \
  tests/test_ai_extended.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/ai/client.py src/ai/generator.py tests/test_ai_client_thinking_contract.py
git commit -m "fix: propagate DeepSeek thinking controls"
```

---

### Task 2: Disable thinking for user-visible prose paths

**Files:**
- Modify: `tests/test_character_creation_deep.py`
- Modify: `tests/test_preset_cast_authority_contract.py`
- Modify: `tests/test_story_continuation_drift_contract.py`
- Modify: `src/game/character_creation.py:1233`
- Modify: `src/game/round/event_generator.py:779`
- Modify: `src/ai/story_rewriter.py:169,275,384,432`

**Interfaces:**
- Consumes: Task 1 `EventGenerator.generate_stream(..., thinking=False)`
- Produces: explicit non-thinking policy for opening, scheduled events, rewrite, and regeneration.

- [ ] **Step 1: Add call-site RED contracts**

Add a hand-written recording generator to `tests/test_character_creation_deep.py` and exercise the real `CharacterCreator.generate_opening_story` method:

```python
def test_opening_story_disables_thinking() -> None:
    class RecordingGenerator:
        def __init__(self) -> None:
            self.calls = []
        def generate_stream(self, **kwargs):
            self.calls.append(kwargs)
            return iter(["opening"])

    generator = RecordingGenerator()
    result = CharacterCreator(generator, language="zh").generate_opening_story(
        character_settings={}, player_name="林岚", life_vision="经营社区影院"
    )
    assert list(result) == ["opening"]
    assert len(generator.calls) == 1
    assert generator.calls[0]["thinking"] is False
```

Extend the existing real-service recording-fake tests:

- `test_scheduled_event_generation_retries_when_story_replaces_preset_cast`: assert every recorded call has `thinking is False`.
- `test_rewrite_story_retries_when_rewritten_story_drifts_from_character_settings`: assert both calls have `thinking is False`.
- `test_regenerate_story_retries_when_story_drifts_from_character_settings`: assert both calls have `thinking is False`.

These four tests jointly cover all six production prose call executions: opening, scheduled initial/retry, rewrite initial/retry, and regeneration initial/retry.

- [ ] **Step 2: Verify focused RED**

Run the four exact node IDs. Expected: failures are missing `thinking` keys or unexpected keyword behavior; existing story outcome assertions remain green.

- [ ] **Step 3: Implement explicit policy at every prose call**

Add `thinking=False` to:

- `CharacterCreator.generate_opening_story` raw stream call;
- scheduled-event `AIClient.call` inside its attempt loop;
- all four `StoryRewriter` provider calls.

Do not change prompts, budgets, temperatures, retries, fallback text, or validation order.

- [ ] **Step 4: Run focused and adjacent GREEN tests**

Run:

```bash
../fix-production-story-generation-20260809/venv/bin/python -m pytest \
  tests/test_character_creation_deep.py \
  tests/test_preset_cast_authority_contract.py \
  tests/test_story_continuation_drift_contract.py \
  tests/test_story_generation_failure_integrity.py -q
```

- [ ] **Step 5: Commit Task 2**

```bash
git add src/game/character_creation.py src/game/round/event_generator.py \
  src/ai/story_rewriter.py tests/test_character_creation_deep.py \
  tests/test_preset_cast_authority_contract.py tests/test_story_continuation_drift_contract.py
git commit -m "fix: disable thinking for story entry points"
```

---

### Task 3: Harden structured-output paths

**Files:**
- Modify: `tests/test_ai_extended.py`
- Modify: `tests/test_ai_modules.py`
- Modify: `src/ai/option_generator.py:101`
- Modify: `src/ai/consistency_validator.py:208,223-425,531`

**Interfaces:**
- Produces: explicit non-thinking policy for option generation and both consistency-validator entry points.
- Produces: `_parse_validation_response` returns a CRITICAL `ValidationResult` for empty, malformed, or non-object JSON.

- [ ] **Step 1: Add option and consistency call-site RED tests**

In `tests/test_ai_extended.py`, add a sequential recording client that returns malformed JSON once and a literal three-option object next. Exercise `OptionGenerator.generate_options_only(..., retry_count=2)` and assert both recorded calls contain `thinking=False`.

In `tests/test_ai_modules.py`, add a simple world model with `build_constraints_text` and `get_established_profile_names`, plus a recording client returning `{}`. Exercise `validate_story` and `validate_with_history` and assert both provider calls contain `thinking=False`.

- [ ] **Step 2: Add fail-closed RED tests**

Replace the old invalid-JSON pass-through characterization with:

```python
@pytest.mark.parametrize("response", ["", "not json", "[]"])
def test_parse_invalid_validation_response_fails_closed(response: str) -> None:
    result = ConsistencyValidator(RecordingClient())._parse_validation_response(response, "zh")
    assert result.passed is False
    assert result.has_critical_issues
    assert result.critical_issues[0].dimension == "validation_response"
    assert result.fix_instructions
```

Add a separate characterization proving valid `{}` remains a pass.

Run the exact tests and confirm missing thinking plus old pass-through behavior cause the RED failures.

- [ ] **Step 3: Implement structured-output policy and parser failure result**

Add `thinking=False` to the option call and both consistency calls.

Add a localized helper in `ConsistencyValidator`:

```python
@staticmethod
def _invalid_response_result(language: str) -> ValidationResult:
    issue = ConsistencyIssue(
        dimension="validation_response",
        severity="CRITICAL",
        description=("一致性校验未返回可解析的 JSON" if language == "zh" else
                     "Consistency validation returned no parseable JSON"),
        fix_suggestion=("重新生成故事并再次执行一致性校验" if language == "zh" else
                        "Regenerate the story and run consistency validation again"),
    )
    return ValidationResult(
        passed=False,
        issues=[issue],
        fix_instructions=(
            "\n\n【一致性校验响应无效】请重新生成故事并再次校验。"
            if language == "zh"
            else "\n\n[INVALID CONSISTENCY RESPONSE] Regenerate the story and validate again."
        ),
    )
```

Change parsing to distinguish valid empty objects from extraction failure:

```python
data = extract_json(response)
if not isinstance(data, dict):
    return self._invalid_response_result(language)
```

The parser exception handler returns the same deterministic result. The outer provider-call exception handlers remain unchanged.

- [ ] **Step 4: Run structured-output GREEN and regressions**

Run:

```bash
../fix-production-story-generation-20260809/venv/bin/python -m pytest \
  tests/test_ai_extended.py \
  tests/test_ai_modules.py \
  tests/test_continuity_ledger_integration.py \
  tests/test_wealth_ledger_integration.py \
  tests/test_gate_gameplay_behavior_no_mock.py -q
```

- [ ] **Step 5: Commit Task 3**

```bash
git add src/ai/option_generator.py src/ai/consistency_validator.py \
  tests/test_ai_extended.py tests/test_ai_modules.py
git commit -m "fix: harden non-thinking JSON generation"
```

---

### Task 4: Integrated verification and stacked PR

**Files:**
- Verify only; no production edits unless a new failing regression requires a test-first fix.

- [ ] **Step 1: Run focused aggregate tests**

Run all modified test files and the PR #265 request contracts together. Record exact counts and warnings.

- [ ] **Step 2: Run repository gates**

Run in order:

```bash
./test.sh preflight
./test.sh all
```

Use this worktree's isolated E2E namespace and ports. Do not borrow production credentials.

- [ ] **Step 3: Audit scope and secrets**

Run `git diff --check`, list the diff against `55ff957a`, and scan changed source/test files for private keys, `sshpass`, bearer tokens, and remote login strings. Expected changed production scope is limited to the interfaces and five paths named by this plan.

- [ ] **Step 4: Self-review realistic mutations**

Confirm at least one RED-proven test fails for each mutation:

- omit thinking in any wrapper retry or raw-stream request;
- omit thinking in any selected initial or retry call site;
- apply thinking globally or to non-V4;
- restore malformed-validator pass-through;
- treat valid `{}` as malformed.

- [ ] **Step 5: Update branch base and publish**

Recheck PR #265. If merged, merge current `origin/main` and rerun affected tests. If still open, keep this as a stacked branch and create a Draft PR with base `codex/fix-production-story-generation-20260809` so the diff contains only this change. Push with tracking, create the PR using the repository template, and report the stacked dependency and validation boundaries.
