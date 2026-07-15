## Context

OptionGenerator has local fallback and validation paths that do not require an AI client: contextual fallback selection, canonical relationship name repair, and missing action-point defaults.

## Goals / Non-Goals

**Goals:** gate story-specific fallback choice sets and persisted relationship-effect normalization.

**Non-Goals:** call the option generation API or change generated option behavior.

## Decisions

- Use a production GameEvent and EventOption objects with an unused `None` client.
- Cover context categories by their first option rather than snapshotting full effect lists.

## Risks / Trade-offs

- [Workflow drift] -> validate ordered workflow parity and the full maintained gate.
