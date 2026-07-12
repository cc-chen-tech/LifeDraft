# P1-4 Exact Save Resume Implementation Plan

## Goal

Loading a save must reconstruct the exact user-visible gameplay phase without
advancing the round or starting a new generation operation.

## State contract

- Add a persisted `resume_view` to `PlayerState` for transient visible phases
  that are not represented by `current_event_data`.
- Store result/summary/ending text and the completed round identity after a
  choice is committed and the backend advances its authoritative round.
- Store generating/failed markers around the durable P1-1 generation worker.
- Keep `current_event_data` authoritative for the options phase.

## Flow

1. The choice pipeline commits history and advances structured time as before,
   then persists the exact result or summary view.
2. Game-load endpoints reuse a live session when one exists, preserving a
   running P1-1 operation. A stale persisted generating marker becomes an
   interrupted/failed view instead of silently starting a second operation.
3. Frontend recovery resolves options, result, summary, generating, and failed
   states explicitly. Existing result text never falls through to initial
   generation.
4. Continuing from result/summary calls an acknowledgement endpoint that clears
   `resume_view`; only then may event generation begin.

## Test-first verification

- Backend: serialization, exact choice-result snapshot, generation markers,
  acknowledgement persistence, and live-session load reuse.
- Frontend: recovery resolver for every phase and play initialization proving a
  result save does not call generation.
- Real DB/API plus browser E2E: save a result page, reload it, verify identical
  phase/week/round and no event-generation request until the continue button.
