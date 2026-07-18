## Context

`src/api/routers/games.py` composes repository-backed persistence with
in-memory session recovery. The selected paths can use the configured SQLite
database directly when each test creates and removes an isolated user/game.

## Goals / Non-Goals

**Goals:**
- Verify owner-scoped state reads and writes through the actual repositories.
- Verify setting fields survive merge and save before the first played round.
- Verify narrative-style storage round-trips using a real database record.

**Non-Goals:**
- Invoke generation providers or construct a live generation session.
- Change router, repository, schema, or legacy mock tests.

## Decisions

- Seed and remove only records belonging to a deterministic private test user.
- Call route functions directly to avoid authentication transport and retain
  database ownership behavior.
- Remove any session-store entry in cleanup so shared process state cannot
  affect later tests.

## Risks / Trade-offs

- [Shared SQLite file] -> Each fixture removes prior records for its test user
  and guarantees cleanup in `finally`.
- [Session cache] -> Tests cover routes without a live session, the persisted
  recovery case that is most relevant to reload behavior.
