## Context

`sse_helpers` updates user-visible state before handing it to the shared game
database. Existing tests cover frames and in-memory state, but not the durable
save/load boundary used after a refresh.

## Goals / Non-Goals

**Goals:** Prove rewritten story text and generation resume views survive real
SQLite persistence without provider calls or test doubles.

**Non-Goals:** Exercise streaming workers, image generation, or alter runtime
database behavior.

## Decisions

- Create an independent game row per test and call the existing helper
  functions with real `GameDatabase` persistence. This verifies the same
  shared SQLite serialization boundary production uses.
- Assert durable field semantics, including preservation of non-text event
  metadata, instead of exact database row implementation details.

## Risks / Trade-offs

- [Global database singleton] -> Tests use independent game rows and assert
  through the public state load path.
- [Broader worker paths trigger providers] -> Scope remains synchronous helper
  calls only.
