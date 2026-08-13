## Context

The async and WebSocket MiniMax TTS paths accept several documented response
shapes. Protocol helpers are pure and can be held stable without credentials
or HTTP calls.

## Goals / Non-Goals

**Goals:**
- Cover nested audio/status responses, base-response errors, file URLs, and
  tar-contained audio extraction.
- Cover protocol URL scheme rejection.

**Non-Goals:**
- Make network requests, modify credentials, or alter provider behavior.

## Decisions

- Build `httpx.Response` values in memory and construct tar archives with
  fixed bytes. This exercises real parsers without external state.
- Assert public parser results and exceptions, including safe fallbacks for
  non-audio tar archives.

## Risks / Trade-offs

- [Protocol schemas can evolve] → Cover accepted nested forms and reject only
  unsupported URL schemes, avoiding over-constraining unrelated fields.
