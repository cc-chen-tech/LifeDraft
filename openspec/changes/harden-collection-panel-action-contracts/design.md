## Context

`CollectionPanel` owns local dialog state and translates user actions into
Zustand store calls. The real child components expose the relevant controls,
while API execution belongs to store tests. A component-level fixture can test
the handoff without a browser, network, or provider.

## Goals / Non-Goals

**Goals:**
- Verify trimmed regeneration feedback reaches the selected item action.
- Verify deletion confirmation routes to the selected entity action.
- Verify landmarks batch action and error dismissal are reachable from the UI.

**Non-Goals:**
- Retest collection HTTP serialization or child dialog layout independently.
- Change mutation behavior, loading UI, or dialog accessibility.

## Decisions

- Render the real panel and real collection children with store actions
  replaced by resolved Jest fixtures. This covers actual event wiring while
  keeping API failures deterministic.
- Seed two characters so initial auto-collection does not interfere with the
  action assertions.
- Assert action arguments, including trimmed feedback and game ID, because
  these fields are the frontend-backend mutation contract.

## Risks / Trade-offs

- [Fixture actions do not prove HTTP behavior] -> existing store/API tests
  retain that responsibility.
- [Icon-only delete controls are harder to locate] -> select the rendered
  destructive action by its class within the real dialog, preserving a
  user-visible workflow test without production test IDs.
