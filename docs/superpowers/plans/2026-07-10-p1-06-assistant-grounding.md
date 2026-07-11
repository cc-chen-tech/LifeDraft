# P1-6 Assistant Grounding Implementation Plan

## Goal

Prevent the story assistant from presenting invented people, events, dates, or
numbers as established game facts. The assistant must read only structured
character settings, committed continuity-ledger records, and completed events;
the chat endpoint must never mutate game state.

## Design

1. Add an assistant grounding module that converts authoritative structured
   state into bounded, source-addressable evidence records.
2. Exclude current story prose, arbitrary round-history prose, pending events,
   conflicts, and future/planned material from assistant evidence.
3. Require the model to return JSON containing a user-facing reply, evidence
   IDs, and an uncertainty flag.
4. Validate every cited ID and every concrete number/date in the reply against
   cited evidence. Reject unsupported answers, retry once with validation
   feedback, then return a deterministic uncertainty response.
5. Short-circuit explicit questions about unknown people before calling the
   model.
6. Replace the router's ad-hoc prose prompt with the read-only grounding
   service. Verify the serialized player state is unchanged across the call.

## TDD sequence

1. Add unit tests for evidence allowlisting, unknown-person handling, supported
   citations, invalid citations, unsupported numbers, retry, and fallback.
2. Extend chat API tests to prove only authoritative evidence reaches the
   model and the player state remains byte-for-byte unchanged.
3. Implement the smallest grounding module and route integration that makes
   those tests pass.
4. Add the regression suite to preflight, then run focused tests, static checks,
   preflight, the full backend layer, and the full E2E layer.

## Non-goals

- Do not write chat answers into stories, history, or the continuity ledger.
- Do not add wealth arithmetic or transaction validation; that belongs to P1-8.
- Do not use uncommitted narrative prose as evidence.
