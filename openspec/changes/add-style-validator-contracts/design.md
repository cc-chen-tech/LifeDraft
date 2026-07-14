## Context

StyleAwareValidator maps a StyleManifest and story text into four dimension
scores. Its behavior is pure and deterministic, enabling direct test coverage
without model, file, database, or browser dependencies.

## Goals / Non-Goals

**Goals:** verify indicators, hook failure, normalized scoring, configured
weights, harness callback output, and fallback behavior.

**Non-Goals:** modify validation rules or evaluate generated text from a model.

## Decisions

- Construct an explicit style manifest and story text that exercises each
  indicator family.
- Assert both success and hook failure outcomes, avoiding fragile full snapshots.
- Keep the test self-contained and add it identically to maintained workflows.

## Risks / Trade-offs

- [Indicator wording can evolve] → Assertions focus on stable returned keys,
  score boundaries, and supplied values.
