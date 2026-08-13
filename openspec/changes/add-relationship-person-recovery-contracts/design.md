## Context

`CharacterCreator.generate_single_relationship_person` adapts AI output into
the relationship state consumed by gameplay. Existing maintained tests cover
other character-creation recovery paths but do not hold this method's
compatibility and fallback shape stable.

## Goals / Non-Goals

**Goals:**
- Cover successful normalization from `relationship_desc` to `relationship`.
- Cover retry after a forbidden vague relationship description.
- Cover the Chinese fallback returned after all three responses are invalid.
- Keep test data provider-free and deterministic at the asserted boundary.

**Non-Goals:**
- Change prompt construction, production retry behavior, or randomized hidden
  attribute selection.
- Modify existing test modules or run the legacy full backend suite.

## Decisions

- Use a small local scripted generator rather than mocks so each response and
  call count is explicit. This follows the maintained-gate no-mock policy.
- Assert stable public fields and retry count, not the randomized hidden
  orientation field. The contract concerns response normalization and recovery.
- Add the test to both workflow lists in the same position to preserve their
  parity.

## Risks / Trade-offs

- [Prompt helper failures can make isolated tests environment-dependent] → Use
  ordinary fixed inputs and exercise the existing prompt helpers without
  asserting their generated prose.
- [Fallback contains randomized hidden data] → Assert only deterministic
  fallback fields that callers rely on.
