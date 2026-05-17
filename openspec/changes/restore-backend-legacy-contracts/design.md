## Context

The last full backend run selected 80 previously failing/erroring tests. One security setup issue has already recovered, leaving clusters around Chinese text normalization, stale music cache internals, era validation helpers, image caching, scene-image SSE, frontend alignment, and older StoryGenerator private methods.

## Goals / Non-Goals

**Goals:**
- Fix same-root-cause failure groups in small batches.
- Prefer production compatibility adapters or current public helpers over broad test rewrites.
- Keep repaired tests outside maintained gates until they pass repeatedly and are judged non-flaky.

**Non-Goals:**
- Restore obsolete implementation internals solely to satisfy stale tests.
- Promote all legacy tests into coverage in one PR.
- Rework unrelated product behavior while repairing test contracts.

## Decisions

- Start with Chinese text normalization because the failures share one missing compatibility entry point and align with current maintained story-quality gates.
- Keep old music cache internals triaged rather than restoring removed cache state until the current music degradation design is reviewed.
- Record each repaired group in tasks so the remaining inventory stays visible.

## Risks / Trade-offs

- Compatibility shims can preserve stale private APIs. Mitigation: only add shims that delegate to current production helpers and keep behavior covered by public tests.
- Fixing full-suite failures can broaden PR scope quickly. Mitigation: stop after coherent groups and rerun targeted tests before wider gates.
