## Context

GameLoop is the orchestration boundary for generated events, lifecycle progression, and retrospective summaries. Its deterministic fallback and summary branches are suitable for maintained tests but remain underrepresented relative to their user-facing risk.

## Goals / Non-Goals

**Goals:**
- Cover localized fallback event shape, state progress, periodic-summary boundaries, and user-summary delegation.
- Use real PlayerState objects and small concrete provider/summary collaborators.
- Preserve synchronized maintained backend workflow lists.

**Non-Goals:**
- Exercise random event-selection behavior, threads, external providers, or browser flows.
- Change GameLoop code, existing tests, timing, or game rules.

## Decisions

- Model collaborators as recording concrete classes, which makes passed context and outputs visible without mock frameworks.
- Assert complete public result shapes where localized fallback text is intentional, and assert selected context fields for generated summaries.
- Keep periodic summaries directly invoked at their boundaries rather than advancing a full game lifecycle; this makes failures local and deterministic.

## Risks / Trade-offs

- [Fallback wording can evolve] → Assert stable localization and option/resource semantics instead of incidental logging.
- [Direct helper invocation misses scheduler integration] → Existing lifecycle tests retain that responsibility; this suite protects the branch behavior itself.
- [Additional maintained modules lengthen the gate] → Tests use no I/O and add negligible runtime.
