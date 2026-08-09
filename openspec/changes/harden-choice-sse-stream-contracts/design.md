## Context

`stream_choice` forwards synchronous choice callbacks into an async SSE stream
and caches story chunks for reconnecting clients.

## Goals / Non-Goals

**Goals:** Verify success ordering, replay cursor identity, and data-error
cache cleanup without providers or databases.

**Non-Goals:** Change SSE production behavior, scheduler implementation, or
existing browser tests.

## Decisions

- Use a deterministic loop collaborator and real `GameLoopSession` cache.
- Consume the async generator and assert public SSE frames, not timing.
- Register the focused test through the shared maintained runner.

## Risks / Trade-offs

- [Global worker pool] → Every test consumes a stream through its terminal
  frame, avoiding timing-based assertions.
