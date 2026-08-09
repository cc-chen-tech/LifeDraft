## Context

The selected suites completed 127 deterministic tests and cover the validation layer that sits between generated text and gameplay state.

## Goals / Non-Goals

**Goals:** fail release validation when generation constraints or recovery behavior regress.

**Non-Goals:** invoke an AI provider or change production behavior.

## Decisions

- Promote the six suites as one validation-and-recovery boundary.
- Verify static hygiene, ordered workflow parity, and complete maintained coverage before commit.

## Risks / Trade-offs

- [Test-order interaction] → run the exact maintained command.
- [Workflow drift] → compare extracted ordered lists.
