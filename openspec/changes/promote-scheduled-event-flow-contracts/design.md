## Context

The maintained gate already includes pure scheduled-event contracts, but it does not include the deterministic flow suite that reaches PlayerState and Commitment integration. That leaves a gap between domain operations and the game-state representation used by gameplay.

## Goals / Non-Goals

**Goals:**
- Add stable PlayerState and Commitment scheduled-event flow coverage to the maintained gate.
- Preserve workflow selection parity and evidence-based coverage thresholds.

**Non-Goals:**
- Change scheduled-event behavior or duplicate provider-dependent gameplay tests.
- Treat this unit-level flow as a replacement for database or browser validation.

## Decisions

- Promote the existing flow suite separately from the pure contract suite because it provides a distinct integration boundary.
- Keep the current 45 percent threshold unless the measured full selection reaches 46 percent.

## Risks / Trade-offs

- [Some assertions overlap lower-level contracts] -> The PlayerState and Commitment scenarios cover paths absent from the lower-level suite.
- [World model is broad] -> Report direct coverage honestly; this promotion validates the tested transition rather than claiming broad world-model coverage.
