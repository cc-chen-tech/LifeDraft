## Context

The current-event recovery suite executes GameLoop loading and RoundEventGenerator fallback behavior with concrete state and a bounded hand-written slow options provider. It passed twice without mocks, external calls, or environment mutation.

## Goals / Non-Goals

**Goals:** Include story restoration, malformed-option tolerance, and fallback-choice behavior in maintained validation.

**Non-Goals:** Change gameplay generation or test remote provider calls.

## Decisions

- Promote the existing flow suite because it targets persisted user state and avoids timing-sensitive external dependencies.
- Retain the current floor unless the expanded selection reaches the next integer.

## Risks / Trade-offs

- [The bounded slow provider has timing] -> It passed twice and uses a small explicit timeout only to exercise the recovery fallback.
