## Context

The maintained suite already checks local music helper functions, while the DB lifecycle is covered only by broader tests that set process environment or use application routes. The service's core decision path is deterministic when supplied with a real SQLite session and local audio fixture.

## Goals / Non-Goals

**Goals:**
- Exercise ready-asset indexing, update, match rejection, and reuse bookkeeping through real ORM relationships.
- Keep the tests isolated from shared database state, provider clients, routes, and environment variables.
- Add the tests to the matching maintained workflow lists.

**Non-Goals:**
- Test MiniMax transport, API routes, background generation, or environment-driven configuration.
- Alter production matching behavior or migrate existing legacy tests.

## Decisions

- Use a new in-memory SQLite engine per test. This gives real persistence semantics without the global `SessionLocal` and table-reset contention of the legacy tests.
- Create only `Game`, `GeneratedMusicAsset`, and library entry data required by the service. Temporary local files provide the audio-existence invariant without mocking the filesystem.
- Assert public service results and persisted fields, including rejection reason codes. Internal timing and provider branches remain out of scope because they require nondeterministic or external state.
- Insert the test beside the existing local-music helper contract in both workflow lists to preserve their required parity.

## Risks / Trade-offs

- [SQLite differs from deployment database] -> The contracts target ORM persistence and service decisions, not database-specific query plans.
- [Scene-fit scoring can evolve] -> Assertions verify deterministic hit/miss behavior and stable metadata rather than brittle exact aggregate scores.
- [Temporary files add filesystem dependence] -> Each test owns its `tmp_path` file and closes its session in `finally`.
