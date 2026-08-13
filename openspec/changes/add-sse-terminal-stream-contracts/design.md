## Context

SSE subscribers replay a durable EventGenerationOperation rather than owning
the worker. Completed, failed, and conflict paths can be exercised using the
real coordinator and small in-process state objects.

## Goals / Non-Goals

**Goals:** cover terminal SSE payloads and recoverable resume state.

**Non-Goals:** start an executor worker, generate text, or trigger images.

## Decisions

- Seed terminal operations through EventGenerationCoordinator so stream calls
  never schedule a worker.
- Use explicit local objects only at the game/session boundary.

## Risks / Trade-offs

- [Terminal timing differs from live workers] → Cover protocol semantics here;
  worker execution remains an integration concern.
