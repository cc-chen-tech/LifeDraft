## Context

The existing test uses hand-written services at provider boundaries and drives the real `RoundChoiceProcessor` through normal resource, wealth, result-view, validation, and custom-choice paths.

## Goals / Non-Goals

**Goals:** Add the deterministic 40-test contract to both maintained selections and verify a full gate run.

**Non-Goals:** Modify production choice behavior or introduce framework mocks, skips, random input, external network, or environment mutation.

## Decisions

- Promote the existing complete contract because it has materially broader behavioral coverage than the focused state contract already in the gate.
- Keep the coverage threshold unchanged unless a strict next-threshold candidate succeeds.

## Risks / Trade-offs

- [Handwritten boundary fakes can drift] -> They are minimal and exercise only the concrete interfaces the processor consumes.
