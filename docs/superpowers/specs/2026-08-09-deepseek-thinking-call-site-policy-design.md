# DeepSeek Thinking Call-Site Policy Design

## 1. Context

Production evidence showed DeepSeek V4 requests ending with `finish_reason=length` at the configured output limit while returning no usable final text. PR #265 adds a request-level `thinking` control and applies `thinking=False` to the five round-story prose calls, but other high-impact paths still rely on the provider default. DeepSeek V4 enables thinking by default, so omission is an implicit policy choice.

This change is stacked on PR #265 at commit `55ff957a`. It must remain a separate branch and later be updated onto `main` after #265 merges.

## 2. Goals

1. Make the request-level thinking policy available through the remaining public AI facade methods.
2. Disable thinking explicitly for the five highest-risk user-facing or structured-output paths:
   - opening story;
   - scheduled/preset event generation;
   - story rewrite and full regeneration;
   - option generation;
   - AI consistency validation.
3. Prevent empty or invalid consistency-validator JSON from being treated as a successful validation.
4. Preserve the current request shape for omitted, `None`, and `True`, and for non-DeepSeek-V4 effective models.
5. Keep the change free of schema, API route, frontend, prompt-content, provider credential, and deployment changes.

## 3. Non-goals

- Do not globally disable thinking in `AIClient`.
- Do not change `max_tokens` budgets.
- Do not add or use production credentials.
- Do not change image prompt analysis, summaries, entity extraction, character-setting generation, decisions, endings, music recommendation, or other lower-priority call sites in this PR.
- Do not introduce reasoning-token telemetry in this PR. The selected high-risk calls explicitly disable thinking; telemetry for deliberately thinking-enabled workloads requires a separate provider-contract design.
- Do not convert transport/provider exceptions in consistency validation from availability-first pass-through to fail-closed. This PR changes only empty or malformed validator output, which was incorrectly interpreted as a valid pass.

## 4. Alternatives

### A. Global `thinking=False` default

Rejected. It is simple but removes provider reasoning from every present and future workload, including tasks that may deliberately need it. It also changes request payloads for unrelated models and callers.

### B. Explicit call-site allowlist

Selected. Public wrappers accept an optional `thinking` argument, while each high-risk caller opts out explicitly. This makes policy visible in code review, preserves backwards compatibility, and keeps unrelated request shapes unchanged.

### C. Keep thinking for consistency validation with a separate reasoning budget

Deferred. This may be appropriate after the provider exposes stable reasoning-token accounting and a separately enforceable reasoning budget. The current 4096-token JSON validator has already produced an empty final response after consuming the budget, so the safer bounded change is `thinking=False` plus fail-closed parsing.

## 5. Interface changes

### `AIClient.call_json`

Add the trailing optional parameter:

```python
thinking: Optional[bool] = None
```

Pass it unchanged to `AIClient.call`. Existing omitted/`None` behavior remains unchanged.

### `AIClient.call_with_retry`

Add the same trailing optional parameter and pass it to `AIClient.call` on every attempt. Retry feedback, callback suppression after the first attempt, model selection, and timeout behavior remain unchanged.

### `EventGenerator` facade

Add `thinking: Optional[bool] = None` to:

- `_call_ai`;
- `generate_completion`;
- `generate_completion_json`;
- `generate_stream`.

The first three methods forward the value to the relevant `AIClient` method. `generate_stream` retains its raw OpenAI stream return contract and adds the same provider-specific request kwargs used by `AIClient`: only an effective model whose lowercase name starts with `deepseek-v4` and an explicit `False` serializes `thinking: {type: disabled}`.

## 6. Call-site policy

| Path | File | Calls covered | Policy |
|---|---|---:|---|
| Opening story | `src/game/character_creation.py` | 1 raw stream | `thinking=False` |
| Scheduled event | `src/game/round/event_generator.py` | initial + retry loop | `thinking=False` on every attempt |
| Story rewrite | `src/ai/story_rewriter.py` | initial rewrite + quick-validation rewrite | `thinking=False` |
| Story regeneration | `src/ai/story_rewriter.py` | initial regeneration + quick-validation regeneration | `thinking=False` |
| Option generation | `src/ai/option_generator.py` | every retry attempt | `thinking=False` |
| Consistency validation | `src/ai/consistency_validator.py` | world-model validation + history validation | `thinking=False` |

No helper should infer policy from prompt text, token budget, or caller name. The policy is explicit at the call site.

## 7. Consistency validation failure semantics

`ConsistencyValidator._parse_validation_response` currently treats an empty response or JSON extraction failure as `ValidationResult(passed=True)`. Replace that behavior with a deterministic failed result:

- `passed=False`;
- one `ConsistencyIssue` with:
  - `dimension="validation_response"`;
  - `severity="CRITICAL"`;
  - a localized description that the validator returned no parseable JSON;
  - a localized fix suggestion to regenerate and validate again;
- non-empty localized `fix_instructions` suitable for the existing story retry path.

Valid JSON behavior is unchanged:

- explicit `should_retry` remains authoritative;
- without `should_retry`, CRITICAL issues fail and warnings pass;
- an empty valid object such as `{}` remains a valid pass because it is parseable JSON and contains no issues.

Provider or transport exceptions remain logged and pass through under the existing availability policy. This distinction prevents malformed model output from masquerading as a successful judgment without turning validator outages into a global story-generation outage.

## 8. Data flow

1. A high-risk caller passes `thinking=False`.
2. Facade methods preserve the value through wrapper and retry layers.
3. The effective model is resolved at the request boundary.
4. DeepSeek V4 requests serialize the disabled-thinking body; non-V4 requests retain their prior shape.
5. Structured response paths parse final output.
6. Consistency validation returns CRITICAL failure for empty or malformed JSON, allowing the existing story retry/failure control flow to act before invalid content is persisted.

## 9. Testing strategy

All production changes use RED-GREEN TDD.

### Request serialization contracts

Use the real OpenAI Python SDK with `httpx.MockTransport` to verify:

- `call_json(thinking=False)` serializes disabled thinking for DeepSeek V4;
- `call_with_retry(thinking=False)` preserves the policy on every attempt;
- `EventGenerator.generate_stream(thinking=False)` preserves its raw stream contract and request body;
- omitted/`None` and non-V4 controls preserve the previous body shape.

### Call-site contracts

Exercise real service methods with recording fakes and assert every relevant provider call receives `thinking=False`:

- opening story;
- both scheduled-event attempts;
- both rewrite attempts;
- both regeneration attempts;
- option retry attempts;
- both consistency-validator entry points.

### Validator semantics

Assert that:

- empty text is CRITICAL failure;
- malformed JSON is CRITICAL failure;
- valid `{}` remains a pass;
- valid warning-only and CRITICAL responses preserve existing behavior;
- the failed parse result provides non-empty retry instructions.

### Regression gates

Run focused interface/call-site tests, adjacent AI and gameplay suites, `./test.sh preflight`, and `./test.sh all` from this worktree. A live-provider smoke remains optional and requires an explicit non-production credential.

## 10. Rollout and safety

- No schema or data migration is required.
- Rollback is a normal code revert.
- Do not merge or publish this stacked branch before PR #265 lands and the branch is updated to current `origin/main`.
- After deployment, observe `finish_reason`, final character count, retry count, consistency parse failures, and persisted generation failure state without logging prompts or credentials.

## 11. Acceptance criteria

- The facade interfaces accept and preserve optional thinking control.
- Every listed high-risk call explicitly sends `thinking=False`.
- No unrelated caller or non-V4 request gains a thinking payload.
- Empty or malformed consistency output cannot produce `passed=True`.
- Existing valid consistency responses retain their semantics.
- Focused, adjacent, preflight, full, and E2E gates are reported separately.
- The diff contains no credentials, deployment mutations, schema changes, frontend changes, or out-of-scope thinking-policy expansion.
