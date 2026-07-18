## Context

`GameLoopSession` retains SSE chunks and generated options so reconnects avoid
regenerating output. `SessionStore` scopes these sessions by user and removes
expired entries. Current tests exercise the basic happy path but do not cover
the state boundaries that matter during reconnects.

## Goals / Non-Goals

**Goals:**
- Exercise replay IDs after the bounded cache trims old chunks.
- Prove option caches are tied to the story text and prefetch flags recover.
- Prove owner-scoped session entries remain separate and expired sessions are
  removed.
- Keep all tests deterministic and free of providers, HTTP, or wall-clock
  sleeps.

**Non-Goals:**
- Change session cache size, key format, expiry duration, or replay protocol.
- Test the browser's EventSource implementation or database restoration.

## Decisions

- Test `GameLoopSession` and a fresh `SessionStore` directly. This isolates
  replay-state invariants from SSE route streaming and makes failures fast to
  diagnose.
- Set `last_access` explicitly and enable immediate cleanup instead of waiting
  for a timeout. This avoids timing-dependent tests.
- Put the new suite in the single maintained-test manifest so local and CI
  gates execute the same risk regression checks.

## Risks / Trade-offs

- [In-memory tests do not prove router serialization] -> SSE route contracts
  remain covered separately by the P1 stream test suite.
- [Tests access cache lifecycle APIs directly] -> assertions use only public
  methods plus the existing expiry control already used by the test suite.
