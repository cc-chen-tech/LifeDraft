## Context

The SSE helper module contains a durable protocol surface that is separable
from worker orchestration. Existing maintained tests exercise state and replay
paths, but the JSON framing and small terminal/retry helpers retain uncovered
branches.

## Goals / Non-Goals

**Goals:**
- Add deterministic unit-level contracts for protocol framing and terminal
  reconnect behavior.
- Keep the suite free of mock frameworks, DB calls, threads, and providers.

**Non-Goals:**
- Test long-running generation workers or replace integration/browser tests.
- Change production SSE behavior.

## Decisions

- Use plain recording objects only for the local session/event protocol, not
  framework mocks.
- Consume asynchronous generators directly with pytest-asyncio so terminal
  events are asserted in protocol order.
- Promote only after direct coverage, static hygiene, workflow parity, and the
  complete 51% maintained gate pass.

## Risks / Trade-offs

- [Protocol serialization is over-specified] → Assert SSE field framing and
  JSON payload semantics rather than key order.
- [Async tests hide a loop dependency] → Keep them limited to generators that
  do not schedule background work.
