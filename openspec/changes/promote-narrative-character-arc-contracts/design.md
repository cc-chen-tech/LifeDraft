## Context

The maintained backend gate uses deterministic suites to progressively raise
reliable measured coverage. `tests/test_narrative_character_arc.py` has nine
passing tests and reaches 64% direct coverage of `CharacterArcEngine` without
network, provider, environment, or mock-framework dependencies.

## Goals / Non-Goals

**Goals:**
- Promote the existing character-arc suite into both maintained workflow
  selections.
- Keep workflow selections exactly ordered-identical.
- Verify the complete maintained gate at its current 50% threshold.

**Non-Goals:**
- Change production behavior or pre-existing test assertions.
- Raise the global coverage threshold without adequate verified margin.
- Add non-deterministic or provider-dependent tests to maintained CI.

## Decisions

- Promote the entire existing file because it checks public state transitions
  and output constraints with deterministic in-memory inputs.
- Append it after the already-promoted narrative suites in both workflows to
  keep the related test surface together and ordering equal.
- Preserve the 50% threshold; one promotion is evaluated by the complete gate,
  rather than assuming direct coverage converts to enough global margin.

## Risks / Trade-offs

- [Existing assumptions are unstable] → Exercise the direct suite and complete
  maintained run under CI-like settings before commit.
- [The workflow lists diverge] → Parse and diff their ordered selections.
- [Coverage gain is insufficient] → Retain the promotion only if the current
  gate passes and continue with separately scoped higher-value suites.
