## Context

ImageService helper branches normalize legacy character settings and resolve
the latest saved game week before provider invocation. They can be tested using
an isolated database session and no image client calls.

## Goals / Non-Goals

**Goals:** cover input normalization and saved-state week precedence.

**Non-Goals:** call providers, storage, or modify production behavior.

## Decisions

- Exercise helpers through ImageService with a real in-memory database.
- Cover structured and legacy settings plus state/initial-state fallback.
- Promote only after complete maintained 51% verification.

## Risks / Trade-offs

- [Constructor configuration changes] → Tests never call generation methods.
