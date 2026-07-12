# P1-5 Atomic Relationship Regeneration Implementation Plan

**Goal:** Prevent relationship feedback regeneration from replacing valid people and summary data with an empty or partial result.

**Root cause:** The completion-screen `regenerateSetting()` sends `relationships` through generic `/character/setting`, even though that prompt explicitly says the path is no longer used. A syntactically valid empty object passes through without validation and is immediately written to Zustand, producing a success log with blank UI.

**Architecture:** Special-case relationship regeneration in the creation hook. Generate every replacement person through `/character/relationship` into a local candidate, generate its summary through `/character/relationships-summary`, validate names/roles/relationship text/uniqueness/summary/cardinality, persist the complete candidate with the existing character-settings PATCH, and only then replace the client store once. Failure at any step discards the candidate and keeps the old state. The feedback card exposes a stable failure message and closes only after success.

## Task 1: RED contracts

- [x] Add a hook test proving relationship feedback currently calls the obsolete generic setting route.
- [x] Add hook tests for a complete candidate, invalid/empty person, empty summary, persistence failure, and no partial store update.
- [x] Add a feedback-card test proving failures keep old content visible and show an actionable error.
- [x] Run focused Jest tests and record the expected failures.

## Task 2: Candidate validation and atomic commit

- [x] Add pure validation helpers for relationship people and the aggregate candidate.
- [x] Generate the same nonzero cardinality as the existing people collection (default three when absent).
- [x] Pass feedback to every person generation request and pass already generated people to later requests.
- [x] Reject missing names, duplicate names, missing role/relationship text, missing summary, and cardinality mismatch.
- [x] PATCH `{ relationships: candidate }` to the existing game before the single client-store update.
- [x] Ensure every provider/validation/persistence failure leaves the old store object untouched.

## Task 3: Visible error semantics

- [x] Make `SettingFeedbackCard` catch regeneration failures, retain the existing content/editor input, and show a safe error.
- [x] Clear stale errors when retrying, cancelling, or succeeding.
- [x] Keep the success log/UI transition after the atomic commit only.
- [x] Run focused hook/card/page tests and strict TypeScript GREEN.

## Task 4: Verification and PR

- [x] Scan for generic relationship regeneration and unvalidated relationship writes.
- [x] Run focused backend character API/creator tests and frontend suites.
- [x] Run `git diff --check` and `./test.sh all`.
- [x] Browser-smoke success and forced-failure flows, proving old data survives failure and a valid candidate replaces it once.
- [x] Audit the P1-5-only diff and prepare draft PR `fix(character): make relationship regeneration atomic`.

## Verification record

- RED: completion feedback used generic `/character/setting`, accepted an empty
  object, and immediately called `updateCharacterSetting("relationships", {})`.
- Focused frontend: 115 hook/card tests passed; the broader create-page group
  passed 173 tests; strict TypeScript passed.
- Focused backend: 74 character API, creator, and character-settings persistence
  tests passed.
- Browser: the forced-invalid candidate kept the old summary/input visible and
  made zero summary/PATCH calls; the valid two-person candidate carried feedback,
  made one PATCH, and replaced the visible summary. Both tests passed in 2.4s.
- Repository gates: preflight, mypy, imports, contract, and DB passed twice. The
  first final E2E attempt correctly stopped on another worktree's global lock;
  after release, the required rerun passed 307 main browser tests (including the
  two new rollback/commit cases), 1 membership music, 1 real character-settings
  persistence, 8 story-voice, 4 MiniMax-audio, and 28 collection/entity tests.
- Diff audit: only the P1-5 hook/card implementation, regression tests, existing
  E2E fixture, and this plan are present.
