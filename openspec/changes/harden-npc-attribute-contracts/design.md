## Context

The validator accepts a story plus a world model with character profiles and
returns structured violations. This is pure local logic.

## Goals / Non-Goals

**Goals:** Verify each contradiction class with a concrete profile container.

**Non-Goals:** Invoke providers, use mocks, or modify validation rules.

## Decisions

- Use SimpleNamespace for the production-required world-model attribute.
- Assert structured violation types as well as pass/fail.

## Risks / Trade-offs

- [Narrative wording changes] -> Match only the validator's documented local
  keyword patterns.
