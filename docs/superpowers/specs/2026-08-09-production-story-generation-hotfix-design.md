# Production Story Generation Hotfix Design

> Status: Approach A approved; written specification awaiting review
>
> Date: 2026-08-09
>
> Branch: `codex/fix-production-story-generation-20260809`

## 1. Incident and evidence

The production `/play` flow completed a round with options but without story text. The frontend correctly rejected that malformed completion and showed the generic retry state.

Read-only production evidence for the affected first round established the exact chain:

1. Production checkout and the running backend files matched `bca973c267e641ce5cde93ae9ec3cf51c6ea46aa`.
2. The configured text model was `deepseek-v4-flash` on the official DeepSeek endpoint, with the constraint harness enabled.
3. All three Expert attempts ended with `finish_reason=length` at `max_tokens=4096` and produced zero story characters.
4. Each empty candidate failed the harness with one CRITICAL issue.
5. On the final attempt, the retry controller declined another retry because the attempt budget was exhausted, but generation continued into option generation.
6. The backend persisted a completed event with `story_len=0` and three options. It did not persist a failed `resume_view`.
7. The frontend rejected the complete event because both streamed and backend story text were empty.

DeepSeek V4 defaults to thinking mode. DeepSeek documents that the output-token budget includes reasoning tokens and that `finish_reason=length` means the generation reached the specified limit. The product's creative-story path expects temperature and repetition penalties to influence generation, while DeepSeek documents that these parameters are ignored in thinking mode.

## 2. Goal

Make first-round story generation produce normal prose with DeepSeek V4 and guarantee that an empty or CRITICAL-invalid story can never be passed to option generation or persisted as a successful event.

Success means:

- DeepSeek V4 round-story prose requests explicitly use non-thinking mode.
- A blank provider result consumes the existing bounded retry budget and never reaches the option generator.
- A CRITICAL-invalid final candidate never reaches the option generator after the harness retry budget is exhausted.
- Valid story generation, streaming, option generation, and existing provider-failure behavior remain unchanged.

## 3. Scope

### In scope

- A per-call AI client control for DeepSeek V4 thinking mode.
- Applying non-thinking mode to every provider call that creates or rewrites round-story prose.
- Enforcing story validity before option generation.
- Focused unit/contract tests that reproduce the production failure.
- Existing preflight and broader regression gates after targeted tests pass.

### Out of scope

- Changing the production model, endpoint, credentials, or deployment environment.
- Increasing the Expert token budget as the primary fix.
- Returning fabricated fallback prose after provider failure.
- Showing raw backend exception strings in the frontend.
- Fixing the independent NPC-age continuity bug.
- Changing first-round opening-continuity prompts.
- Refactoring general SSE recovery or frontend error presentation.
- Deploying the hotfix to production.

These exclusions keep the branch reversible and directly tied to the observed incident.

## 4. Design

### 4.1 Per-call DeepSeek thinking control

`AIClient.call()` and its internal/fallback paths will accept `thinking: Optional[bool] = None`. When the effective model is a DeepSeek V4 model and the caller supplies `False`, the OpenAI-compatible request will include:

```python
extra_body={"thinking": {"type": "disabled"}}
```

When the control is omitted, existing request behavior is unchanged. For non-DeepSeek-V4 models, no provider-specific body is emitted. This avoids silently changing unrelated AI tasks or future providers.

The control must propagate through:

- normal and streaming chat completions;
- model-fallback calls;
- truncation-recovery continuation calls.

No reasoning content is logged or exposed.

### 4.2 Round-story calls use non-thinking mode

Every `StoryGenerator` call that creates or rewrites round prose will pass `thinking=False`:

- initial round draft;
- quick-consistency rewrite;
- story-shape rewrite;
- repeated-story rewrite;
- AI-consistency rewrite.

Option generation and other AI features are not changed in this hotfix. The existing Expert story budget remains 4096 tokens because non-thinking mode reserves that budget for final prose instead of hidden reasoning.

### 4.3 Empty-story guard

Immediately after normalization, a blank story is an invalid provider result. The attempt raises `ValueError("Story provider returned empty text")` before quick validation, harness validation, consistency validation, or option generation.

The outer bounded attempt loop remains authoritative:

- attempts remain limited by the configured quality profile;
- a later valid attempt may succeed;
- exhausting attempts raises the existing `StoryGenerationFailure` path;
- no fake prose or generic options are created for a blank story.

### 4.4 Final harness guard

When harness validation reports a CRITICAL failure:

- if retry budget remains, preserve current retry behavior;
- if retry budget is exhausted, raise `ValueError("Story harness validation failed after final attempt")` instead of continuing to option generation.

The guard follows the existing `enforce_validation_on_all_attempts` profile contract. It prevents the exact malformed completion observed in production while leaving warning-only candidates eligible to continue under the current Expert policy.

### 4.5 Failure behavior

If non-thinking mode still fails to produce a valid story, the backend uses the existing durable failure contract:

```text
StoryGenerationFailure
  -> operation failed
  -> resume_view.phase = failed
  -> SSE event:error
```

This is intentionally preferable to a successful event with empty story text. Frontend error-copy improvements remain a separate change.

## 5. Test design

All production changes follow red-green TDD.

### Test 1: DeepSeek V4 request control

Exercise the real `AIClient` request-building path with a fake external completion transport. Assert that a round-story call requesting `thinking=False` sends the documented DeepSeek body in both streaming and non-streaming paths, while an omitted control preserves the existing request shape.

The test catches removal, inversion, or accidental global application of the thinking control.

### Test 2: production empty-story reproduction

Use a deterministic client that returns blank story text for every Expert attempt and a real harness configuration. Assert:

- the bounded story attempts are consumed;
- `StoryGenerationFailure` is raised;
- the option generator is never called;
- no `GameEvent` with an empty `event_description` is returned.

The test catches the observed `story_len=0, options=3` success path.

### Test 3: terminal CRITICAL validation

Use non-empty candidates and a deterministic validation pipeline that reports a CRITICAL failure on every attempt. Assert that the final attempt raises and the option generator is never called.

The test catches the retry-controller fall-through independently from the empty-provider-output guard.

### Regression gates

After targeted tests are green:

1. Run the affected backend test files.
2. Run `./test.sh preflight` with the worktree's Python 3.11 environment.
3. Run `./test.sh all` only from this isolated integration worktree.
4. Exercise the local create-to-first-round browser path without production credentials or state.

## 6. Operational safety

- The branch does not edit production state, credentials, environment files, or containers.
- Production evidence remains summarized as lengths, phases, counts, timestamps, and sanitized error categories.
- A later deployment must verify the backend revision and perform a fresh first-round smoke test; local green tests alone are not deployment proof.
- Rollback is a normal code rollback because the change introduces no schema or data migration.

## 7. Acceptance criteria

The hotfix is ready for review when:

- all three targeted regression behaviors are demonstrated red before implementation and green afterward;
- valid existing story-generation tests remain green;
- no blank story can reach option generation in the covered production path;
- DeepSeek V4 story requests explicitly disable thinking without changing unrelated provider requests;
- preflight and full-gate results are reported separately;
- the diff contains no NPC-age, frontend-copy, prompt-continuity, deployment, or credential changes.
