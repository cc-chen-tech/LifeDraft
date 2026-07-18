## Context

The scheduled-event generator uses persisted commitment records and player state to create a constrained prompt. It can be tested without model calls because prompt construction is deterministic.

## Goals / Non-Goals

**Goals:** Verify commitment aggregation, cast authority, time coordinates, and localized identity constraints.

**Non-Goals:** Invoke AI generation, stream output, or test retry scheduling.

## Decisions

- Instantiate the generator with inert collaborators and call `_build_scheduled_event_prompt` directly.
- Assert durable semantic segments rather than full prompt text.

## Risks / Trade-offs

- [Prompt wording changes] -> Assertions focus on persisted field values and required constraint headings.
