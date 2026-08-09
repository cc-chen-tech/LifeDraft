## Context

SceneImageService prepares character information before any image client call.
This pure logic selects cited NPCs and family members and derives layout-safe
descriptions from both structured and legacy settings.

## Goals / Non-Goals

**Goals:** verify roster completeness, deduplication, compatibility, and layout
text without constructing a provider client.

**Non-Goals:** generate images, access a database, or alter prompt behavior.

## Decisions

- Instantiate the service with `__new__` because selected helpers need no
  constructor state.
- Assert the public helper output rather than provider-call internals.

## Risks / Trade-offs

- [Prompt text can evolve] → assert inclusion, ordering, and stable semantic
  clauses rather than full prompt snapshots.
