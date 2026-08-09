## Context

Round generation has a durable operation separate from an HTTP stream. A
subscriber that reconnects after completion must resume from its event cursor
without starting a new worker or replaying already seen content.

## Goals / Non-Goals

**Goals:**
- Exercise the completed replay path using `EventGenerationOperation`.
- Verify SSE status, cursor filtering, chunk ID, and terminal payload order.
- Keep the test entirely in memory and provider-free.

**Non-Goals:**
- Testing background worker scheduling, provider generation, or timeout timing.

## Decisions

- Use the real durable operation and a small in-memory coordinator holder;
  this validates replay semantics rather than a fabricated snapshot.
- Parse each emitted SSE payload as JSON so event framing and consumer data are
  tested together.

## Risks / Trade-offs

- [Async test complexity] -> The operation is completed before subscription, so
  there is no wall-clock wait or thread scheduling dependency.
