## Context

CharacterCreator makes local corrections after generation responses are available, including life-vision alignment, retry-safe wealth validation, birth-year calculation, and bounded starting attributes.

## Goals / Non-Goals

**Goals:** gate deterministic correction of persisted character setup values.

**Non-Goals:** make provider requests or alter generation behavior.

## Decisions

- Use a minimal deterministic generator returning supplied JSON data.
- Exercise public CharacterCreator methods and assert returned domain values.

## Risks / Trade-offs

- [Workflow drift] -> validate ordered workflow parity and the full maintained gate.
