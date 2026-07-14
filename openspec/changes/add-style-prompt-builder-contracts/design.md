## Context

StyleAwarePromptBuilder is a pure adapter from StyleManifest dataclasses to
textual generation constraints. It has no provider or database dependency, so
complete branch behavior can be verified with explicit in-process manifests.

## Goals / Non-Goals

**Goals:** prove the complete manifest output, optional field behavior, chapter
guidance, per-scene temperature, and max-token character budgeting.

**Non-Goals:** load style files, call story generators, change style semantics,
or modify the historical test module.

## Decisions

- Build explicit dataclass manifests inside the tests rather than consuming a
  shared fixture, keeping the maintained suite self-contained.
- Assert representative output clauses from each style dimension instead of
  duplicate all-text snapshots.
- Cover the no-style fallback and sparse style behavior to protect optional
  manifest fields.
- Add the new suite to both workflows at the same ordered position.

## Risks / Trade-offs

- [Prompt wording is intentionally editable] → Assert contract markers and
  supplied values, not the entire assembled string.
- [Global coverage gain may be small] → This targets a low-coverage pure module
  with a high semantic role in story generation.
