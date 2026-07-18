## Context

Story voice reading persists per-user settings, browser-fallback jobs, and
provider audio assets. The service decides whether the client must use browser
speech or can recover a stored audio asset, so its response fields form a
frontend-backend contract.

## Goals / Non-Goals

**Goals:**

- Exercise the service and repository together against the existing SQLite
  schema, with each test rolling back its own work.
- Cover provider fallback, deterministic audio persistence and reuse, job
  recovery, settings updates, and validation boundaries.
- Avoid external TTS transport, environment mutation, random identifiers, and
  test doubles.

**Non-Goals:**

- Test API authentication or browser audio playback.
- Change persistent models, provider implementation, or existing tests.
- Make an external voice provider available in local test runs.

## Decisions

- Use the repository's configured `SessionLocal` and `init_db` rather than a
  fake repository. This checks ORM relationships and stored JSON fields that a
  unit double would not reveal.
- Pass browser and deterministic providers explicitly. This makes the contract
  deterministic without changing process environment or invoking remote TTS.
- Use static, rollback-scoped user identities. The tests never commit and each
  session is rolled back in `finally`, so repeated maintained runs remain
  isolated without random identifiers.

## Risks / Trade-offs

- [Configured SQLite can contain artifacts from prior local runs] -> Each test
  inserts only rollback-scoped data and uses unique static identifiers for this
  module.
- [Service-level coverage does not prove browser control behavior] -> Browser
  experience tests remain responsible for UI interaction and media playback.
