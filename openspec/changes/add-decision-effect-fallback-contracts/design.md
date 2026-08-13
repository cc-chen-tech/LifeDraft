## Context

`process_decision` applies numeric effects, synchronizes relationship state,
records decisions, and optionally creates result prose. The provider-backed
path is not required to prove its deterministic business rules.

## Goals / Non-Goals

**Goals:**
- Verify positive and negative relationship-derived character effects.
- Verify interaction context, invalid selection validation, and fallback text.
- Verify a local failing provider degrades without network or mocks.

**Non-Goals:**
- Do not modify decision logic, event triggers, or model prompts.
- Do not execute remote generation.

## Decisions

- Use `PlayerState` and `CharacterState` directly for real state semantics.
- Use a tiny local provider that raises from `generate_completion`; this
  exercises the public call boundary without a mock framework.
- Assert returned effects and state history rather than logger output.

## Risks / Trade-offs

- [Character trigger thresholds are domain-specific] → Test derived effects and
  context separately from threshold-trigger outcomes.
- [Fallback prose changes] → Assert the relevant localized effect fragments.

## Migration Plan

This is additive. The new suite is added to both maintained workflow lists;
revert removes the suite and entries only.

## Open Questions

None.
