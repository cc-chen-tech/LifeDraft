## Context

`EndingEvaluator` delegates narrative prose to an optional generator and falls back to a localized template on failure.

## Goals / Non-Goals

**Goals:** verify generated prose is guarded and failures retain a localized ending.

**Non-Goals:** invoke an AI provider or change prompt generation.

## Decisions

- Use deterministic generators exposing `generate_completion`.
- Assert provider input includes final-state context while avoiding brittle whole-prompt equality.

## Risks / Trade-offs

- [Guardrail policy can evolve] → assertions target observable normalized prose and fallback behavior.
