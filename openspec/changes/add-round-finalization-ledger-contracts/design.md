## Context

RoundFinalizer coordinates the final state transition at the end of a game week. It uses a wealth ledger for monetary bonuses, emits a weekly summary record, applies decay, advances time, and independently maintains periodic summary records.

## Goals / Non-Goals

**Goals:**
- Cover the synchronous finalization path with a real PlayerState and WealthLedger.
- Cover deterministic four-week and yearly record thresholds.
- Keep enrichment asynchronous behavior outside this unit-level maintained contract.

**Non-Goals:**
- Change reward semantics, start threads, call extraction services, or test external AI clients.
- Modify legacy tests.

## Decisions

- Use a small RoundFinalizer subclass that records enrichment dispatch instead of starting a thread. This preserves finalizer behavior while preventing external work.
- Use concrete summary and character-completion collaborators, with only the public methods actually consumed by RoundFinalizer.
- Assert persisted wealth transaction metadata, summary records, resource changes, and week advancement.

## Risks / Trade-offs

- [Thread dispatch is not exercised] → Its non-blocking behavior remains covered by dedicated legacy/integration tests; this suite focuses on synchronous data integrity.
- [Ledger validation could change text] → Use a summary with no unsupported monetary claim and assert ledger records directly.
