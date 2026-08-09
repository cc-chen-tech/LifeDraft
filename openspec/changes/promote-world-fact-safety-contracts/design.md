## Context

`qualify_generated_world_facts` is a small, high-impact safety function. The
candidate suite deterministically tests precise claim qualification,
idempotency, and pass-through of qualitative fiction, and comparison against
the current maintained coverage report identifies 11 newly covered statements.

## Goals / Non-Goals

**Goals:**
- Include the deterministic safety suite in both maintained workflows.
- Preserve ordered selection parity and the verified 51% coverage threshold.

**Non-Goals:**
- Modify safety wording, prompt behavior, or existing test assertions.
- Add real-world data, external calls, or environment-based behavior.

## Decisions

- Promote the whole existing no-mock contract file because it protects a
  user-facing factual-boundary rule with isolated inputs.
- Append the file near other world-model contract tests in both workflow lists.
- Keep the threshold at 51%; this small promotion is evaluated for coverage
  gain but is not assumed to justify the next integer increase.

## Risks / Trade-offs

- [Prompt text changes make tests brittle] → Assertions focus on required
  safety concepts rather than complete prompt text.
- [Workflow selections diverge] → Parse and compare ordered selections.
- [Coverage contribution overlaps unexpectedly] → Confirm the full maintained
  result before commit.
