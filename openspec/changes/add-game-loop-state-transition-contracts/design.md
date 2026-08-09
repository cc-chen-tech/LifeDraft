## Context

The tests use a concrete GameLoop and PlayerState without generating AI events or summaries.

## Goals / Non-Goals

**Goals:** gate weekly decay and event cleanup invariants.

**Non-Goals:** change game behavior or invoke AI generation.

## Decisions

- Advance only from week one to avoid summary boundaries.

## Risks / Trade-offs

- [Workflow drift] → validate ordered workflow parity and full maintained execution.
