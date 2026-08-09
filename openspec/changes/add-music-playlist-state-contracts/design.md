## Context

Playlist state preserves current playback while recommendations refresh, inserts
generated music into the upcoming queue, and stores player controls across
navigation. These transitions are best validated below the browser but against
real persistence.

## Goals / Non-Goals

**Goals:**

- Validate queue semantics through pure policy tests.
- Validate service state transitions with a disposable in-memory SQLite schema.
- Avoid network, environment mutation, global database state, random IDs, and
  test doubles.

**Non-Goals:**

- Test music recommendation providers, API authentication, or browser audio
  rendering.
- Change playlist implementation or existing tests.

## Decisions

- Use a new in-memory SQLite engine per service test. `MusicPlaylistService`
  commits internally, so this keeps real ORM behavior while avoiding persistent
  state and rollback assumptions.
- Test title-family deduplication through the public queue policy, including
  known cover/live variants. This protects the user-facing queue rather than
  regex internals alone.
- Assert whole state transitions after merge, sync, advance, and wraparound to
  make frontend-consumed fields stable.

## Risks / Trade-offs

- [In-memory SQLite differs from deployed storage timing] -> The tests focus on
  ORM transaction semantics and serialized fields, while API/browser tests
  retain responsibility for route and playback behavior.
