## Context

`stream_round_event` is the browser-facing adapter over a durable
`EventGenerationOperation`. It must replay only frames newer than the supplied
cursor and finish with one terminal frame. A worker conflict or failure must not
leave the browser waiting for a completion event.

## Goals / Non-Goals

**Goals:**
- Assert frame order and payloads with the real operation state model.
- Avoid threads, network providers, and timing sleeps in protocol tests.
- Run the new tests in the maintained backend gate.

**Non-Goals:**
- Change SSE implementation behavior.
- Test HTTP transport buffering or browser EventSource rendering.

## Decisions

- Seed real `EventGenerationOperation` instances into terminal states and patch
  only the operation-acquisition seam.
- Parse emitted frames as SSE event type, optional id, and JSON payload rather
  than making substring-only assertions.
- Keep cursor and terminal tests independent so failures identify a specific
  protocol regression.

## Risks / Trade-offs

- These tests validate the server protocol, not proxy timeouts or browser
  reconnection behavior. Those remain E2E concerns.
