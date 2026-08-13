## Context

Location, career, commitment, and causal update methods require only `week` and `world_model_data` attributes.

## Goals / Non-Goals

**Goals:** cover actual dict-state transitions without doubles.

**Non-Goals:** call AI-dependent updater methods or alter production behavior.

## Decisions

- Use `SimpleNamespace` with concrete nested data and verify cleanup behavior.

## Risks / Trade-offs

- [Heuristic commitment matching] -> use unambiguous descriptions and parties.
