## Context

The save-point repository separates manually named rewind checkpoints from
automatic state snapshots and enforces game ownership for every access path.

## Goals / Non-Goals

**Goals:** Verify lifecycle, visibility, and access control through the real
SQLite repository.

**Non-Goals:** Exercise HTTP handlers, frontend rewind controls, or alter the
save-point implementation.

## Decisions

- Use real user, game, and state rows with the repository's own session
  factory, then assert only its public return payloads.
- Include both manual and automatic states to prevent the two timeline views
  from silently collapsing into one another.

## Risks / Trade-offs

- [Shared test database] -> Create independent owner and game rows for each
  test without relying on provider or network state.
