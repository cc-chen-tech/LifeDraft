## Context

The collection system must combine story-derived entities with persisted
metadata and avoid delaying visible completion on a detail refresh. The
existing provider-free test file exercises those boundary contracts with real
parsers and source-level consumer checks.

## Goals / Non-Goals

**Goals:**
- Promote the verified file into both maintained selections.
- Require exact workflow parity and two complete coverage measurements.

**Non-Goals:**
- Change entity recognition heuristics or provider calls.
- Change the existing contract test file.

## Decisions

- Promote the existing file unchanged because it is deterministic, has passed
  twice, and contains no prohibited gate constructs.
- Keep coverage-floor changes evidence-driven; no threshold raise is assumed.

## Risks / Trade-offs

- [Source consumer checks can be brittle] -> They are paired with behavioral
  parser checks and protect a documented UI completion regression.
