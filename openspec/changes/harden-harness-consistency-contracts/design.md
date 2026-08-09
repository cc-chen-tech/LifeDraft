## Context

The maintained backend suite currently covers core API, persistence, and selected game-state contracts, but omits standalone narrative consistency validators. A legacy aggregate validator test module has conditional imports and module-level skip behavior, so it is not suitable for a stable coverage gate. A separate temporal contract suite already exists and has no doubles or skip behavior.

## Goals / Non-Goals

**Goals:**
- Exercise temporal, causal, and information-boundary validation through their public APIs with deterministic local state.
- Keep both maintained workflow selections ordered identically.
- Raise the coverage floor only from repeatable measured evidence.

**Non-Goals:**
- Change validator heuristics, application behavior, provider integrations, or the legacy aggregate test module.
- Cover all harness validators in this batch.

## Decisions

- Promote the existing temporal contract suite rather than duplicate it. It already covers conversion, seasonal and age constraints, and the public wrapper without doubles.
- Add a new focused file for causal and information contracts. Direct dictionaries and `SimpleNamespace` model the minimal runtime context while preserving the public validator contract; no mocks, monkeypatches, databases, randomness, or timing are introduced.
- Treat workflow symmetry as a contract. The coverage and maintained-test workflows receive the same new test paths in the same order.
- Keep the current floor unless two full maintained runs demonstrate the next integer percentage. This avoids a threshold that is sensitive to incidental coverage accounting.

## Risks / Trade-offs

- [Text heuristics are intentionally approximate] -> Assert explicit structured outcomes for unambiguous inputs rather than brittle incidental wording.
- [A growing maintained suite adds execution time] -> Limit this change to pure in-process validators and retain the existing selected suite instead of adding the legacy aggregate module.
- [Coverage can vary with test selection] -> Run the exact maintained command twice before changing the floor.
