# P1-7 Authoritative Continuity Ledger Implementation Plan

> Base: `codex/p1-04-exact-save-resume`
> Branch: `codex/p1-07-continuity-ledger`
> Scope: P1-7 only. Assistant grounding and wealth accounting remain P1-6 and P1-8.

## Goal

Persist an authoritative, source-linked continuity ledger and use it before and after narrative generation so character identity, dates, completed events, health, and relationships cannot silently drift across weeks.

## Task 1: Define the ledger contract with failing tests

- Add `tests/test_continuity_ledger.py`.
- Specify backward-compatible serialization and seeding from player name, age, key people, family, roles, relationships, and deceased status.
- Specify prompt snapshot output and deterministic conflict results for wrong dates, wrong ages, renamed/repurposed roles, active deceased characters, and rollback of completed facts.
- Specify legal mutable updates with source event IDs and conflict audit records.

## Task 2: Persist the authoritative ledger

- Add `continuity_ledger` to `PlayerState` with an empty versioned default.
- Seed it during game initialization without changing existing character settings or world-model fields.
- Implement `ContinuityLedger.from_player_state`, `to_dict`, and `persist` with legacy-save migration.
- Keep entries bounded and source-linked by week, round, date, event ID, and story hash.

## Task 3: Inject and enforce ledger constraints

- Attach the ledger to `WorldModel` and include the relevant snapshot in generation constraints.
- Run deterministic ledger validation before optional AI consistency validation, including fast quality mode.
- Convert deterministic conflicts into CRITICAL consistency issues and retry instructions.
- Keep validation fail-closed for authoritative conflicts but fail-open for ledger parsing errors, with diagnostic logging.

## Task 4: Commit only source-backed changes

- Record each completed choice as a committed timeline event after the round result is accepted.
- Record validated fact, career, location, commitment, health, and relationship changes with their source event.
- Reject candidate updates that conflict with immutable identities or time ordering; retain prior ledger state and append a bounded conflict record.
- Do not introduce transaction/balance logic in this PR.

## Task 5: Four-week regression and gates

- Add a deterministic 12-round regression that preserves canonical names, age/date progression, completed actions, health transitions, and relationship sources.
- Verify conflicting generated stories do not mutate the ledger.
- Run focused backend tests, preflight, mypy, full backend, and full browser E2E.
- Push the branch and open a stacked draft PR based on `codex/p1-04-exact-save-resume`.
