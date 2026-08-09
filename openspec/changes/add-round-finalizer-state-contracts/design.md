## Context

`RoundFinalizer` mixes synchronous player-state bookkeeping with background
enrichment. The synchronous portion can be tested with concrete state and
small local collaborators, avoiding threads and extraction services.

## Goals / Non-Goals

**Goals:**
- Verify synchronous summary fallback, delegation, round information, decay,
  and periodic summary records.
- Keep contracts local, deterministic, and no-mock.

**Non-Goals:**
- Do not start enrichment threads or run item/landmark extraction.
- Do not alter finalizer implementation or generated prose.

## Decisions

- Use local collaborator classes with explicit methods for summary generation,
  story compression, and character completion.
- Use real `PlayerState` for round information and decay, and small state
  namespaces only where periodic history lacks domain validation requirements.
- Test four-week and yearly aggregation directly to avoid asynchronous timing.

## Risks / Trade-offs

- [Periodic data shape may evolve] → Assert stable record keys and source
  summary inclusion, not log messages.
- [Thread paths remain untested] → Keep them in dedicated integration work;
  this change protects the deterministic core.

## Migration Plan

Add the suite to both maintained workflow lists. Reverting removes only new
tests and configuration entries.

## Open Questions

None.
