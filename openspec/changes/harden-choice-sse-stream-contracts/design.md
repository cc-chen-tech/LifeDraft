## Context

`stream_choice` bridges a synchronous game-loop choice into an async SSE response, caches story chunks for reconnection, and must clear cache on terminal data errors. These branches can run with a deterministic local game-loop collaborator and a real `GameLoopSession` cache.

## Goals / Non-Goals

**Goals:**
- Verify successful status, story, and complete frames.
- Verify cached story replay preserves cursor identity.
- Verify data errors produce an error frame and clear replay cache.

**Non-Goals:**
- Invoke game generation, databases, or external providers.
- Change thread-pool implementation or existing tests.

## Decisions

- Use a small deterministic loop collaborator implementing only the choice callbacks and a no-op state accessor.
- Use the real session cache implementation and consume the async generator to completion.
- Assert public SSE event payloads rather than scheduler timing.

## Risks / Trade-offs

- [Thread pool is global] -> each generated stream reaches a terminal event; existing lifecycle tests retain ownership of pool shutdown.
- [Worker scheduling changes event timing] -> assert event content and required ordering, not microsecond timing.

## Migration Plan

No migration is required; the change adds tests only.
