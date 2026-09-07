# TTS Playback Reliability Implementation Plan

> Execute using superpowers:subagent-driven-development and test-driven-development. Write regression tests, observe the intended failure, then implement and run the relevant suites. The root worker owns integration and the full test runner.

**Goal:** Repair the observed lock/timeout/fallback incident, preserve playable audio during partial failure, eliminate extra AI planning from first playback, and recover abandoned tasks safely.

**Architecture:** Keep existing database/job/segment APIs and cache, make polling read-only, isolate synchronous I/O, use bounded worker recovery and client retries. Separate connection failure from synthesis and playback failure.

**Stack:** FastAPI, synchronous SQLAlchemy/SQLite, MiniMax WebSocket, React, Jest, pytest, Playwright.

**Spec:** docs/superpowers/specs/2026-09-08-tts-playback-reliability-design.md

## Engineering decisions

The design was a proposal, not an instruction to migrate every protocol. Implement incident closure without introducing a new progress schema, paragraph-to-unit mapping, or changing production journal mode. Existing stable paragraph indexes, exact lease fencing and cache identities remain compatible. Those three extensions need separate data migration/performance evidence; adding them to a reliability repair increases regression risk without being necessary to stop this incident. Preserve this decision in the PR scope.

## Task 1: Playback recovery

- [x] Add component/API regressions for a transient poll timeout followed by ready, partial failed job with ready audio, no unsolicited browser speech, original voice recovery, cancellation on voice/story change, and completed chapter not resetting current audio.
- [x] Run new tests against baseline and retain red evidence.
- [x] Implement retrying connection state while preserving queue/position, explicit system speech choice and recovery, identity-aware cancellation, bounded/coalesced progress saving. Reuse existing compatible response fields.
- [x] Run entire component suite, API suite, types and focused lint; record green evidence.

## Task 2: Durable generation recovery and first playback

- [x] Add DB/service regressions for read-only polling under a held SQLite writer lock, single-segment failure preserving ready segments, retry skipping valid segments, assembly failure preserving queue, stale recovery/late-worker fencing, no AI plan request when absent on playback.
- [x] Observe red, then make GET genuinely read-only; use explicit background recovery, preserve ready segments throughout retry/expiry/processing, and commit plan writes with fencing.
- [x] Add bounded recovery loop outside the request event loop; keep existing lease token model if its fencing remains sound. No session sharing between threads and no open write transaction during synthesis.
- [x] Use existing valid plan or deterministic plan on demand. Invalid explicit plans remain errors. Do not change segment boundaries in this repair.
- [x] Run affected service, route, DB and narration-plan suites.

## Task 3: I/O isolation and transport deadlines

- [x] Reproduce lock contention using file-backed SQLite with independent connections and concurrent ASGI requests. Test health remains responsive during a progress write, progress has a bounded structured failure, and recovery succeeds after lock release.
- [x] Change blocking voice routes to synchronous execution; scope short lock waits and transaction retries to progress operations. Keep authentication/access controls and shared request-session lifecycle intact.
- [x] Add protocol tests proving WebSocket receive has a real timeout and heartbeat/cancellation budget; preserve protocol completion and error cause.
- [x] Implement transport deadlines and diagnostic exception logging, without retrying already-successful provider calls for DB failures.

## Task 4: Integration, review and PR

- [x] Review changed contracts across Tasks 1–3, update obsolete tests only where the intended user behavior changed.
- [x] Run focused backend/frontend tests, then ./test.sh all, all Python tests and full frontend Jest tests as applicable; isolate databases and avoid competing heavy runners.
- [x] Run typecheck/build/lint and browser regression for timeout/recovery where needed; independently review the full diff.
- [x] Fix and retest actionable findings. Delivery uses only this worktree's changes and a PR against main with exact validation and limitations; do not merge/deploy.

## Verification record

Tests were added first and observed failing on the intended behavior before implementation. The initial frontend regressions caught unsolicited fallback, the whole-job deadline, missing cancellation, overlapping progress writes and audio source replacement. File-backed SQLite tests reproduced an event-loop stall and unstructured lock failure. Real local WebSocket tests reproduced unbounded receives; a follow-up regression caught non-audio messages incorrectly extending the idle deadline. Recovery tests cover partial synthesis/assembly failure, asset identity, abandoned leases, stale-worker fencing and bounded admission.

Independent review found three additional playback defects: cumulative scene seeking, complete-queue replay, and stale media events during a new story hash. Each was reproduced before repair, including metadata-ready cross-source seek and mixed-source replay variants. The final source review has no remaining actionable P1/P2 findings.

| Final verification | Result |
| --- | --- |
| `env -u DATABASE_URL ./test.sh all` | PASS: preflight, strict types/mypy, imports, 278 contract tests, 132 DB tests, production build and core browser tests |
| Core browser tests | 323 passed, 1 skipped, 0 flaky; includes a real 20-second poll timeout followed by original-voice audio playback |
| `env -u DATABASE_URL ./test.sh full-backend` | 5044 passed, 1 skipped, 4 expected failures |
| `env -u DATABASE_URL ./test.sh frontend` | TypeScript passed; 2117 unit tests and 2 integration tests passed |
| Mobile Safari / WebKit audio transport suite | 6 passed, including the real 20-second timeout recovery; reused the final production build |
| Final focused playback suite | 58 passed; strict TypeScript and focused ESLint passed |
| File-lock / WebSocket / protocol regression group | 32 passed |

The core browser skip is the protected model-smoke report test; it requires `MODEL_SMOKE_REPORT`. Existing backend skips/expected failures remain visible. Live paid-provider/model-smoke and manual production exploration were not run; deterministic browser fixtures decode real WAV audio, and WebSocket timeout tests use a local transport server. No production changes, schema migration, journal-mode change, merge or deployment were performed.

Full backend verification also exposed eight failures reproducible on untouched `origin/main`: seven incomplete OpenAI response mocks and one scanner false positive on a redaction regex literal. The PR repairs those test fixtures, keeps real telemetry active, and adds scanner regressions proving credentials adjacent to the regex are still detected. No corresponding AI production behavior was changed.
