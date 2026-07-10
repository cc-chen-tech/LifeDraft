# P1-5 Atomic Relationship Regeneration Implementation Plan

**Goal:** Prevent relationship feedback regeneration from replacing valid people and summary data with an empty or partial result.

**Root cause:** The completion-screen `regenerateSetting()` sends `relationships` through generic `/character/setting`, even though that prompt explicitly says the path is no longer used. A syntactically valid empty object passes through without validation and is immediately written to Zustand, producing a success log with blank UI.

**Architecture:** Special-case relationship regeneration in the creation hook. Generate every replacement person through `/character/relationship` into a local candidate, generate its summary through `/character/relationships-summary`, validate names/roles/relationship text/uniqueness/summary/cardinality, persist the complete candidate with the existing character-settings PATCH, and only then replace the client store once. Failure at any step discards the candidate and keeps the old state. The feedback card exposes a stable failure message and closes only after success.

## Task 1: RED contracts

- [ ] Add a hook test proving relationship feedback currently calls the obsolete generic setting route.
- [ ] Add hook tests for a complete candidate, invalid/empty person, empty summary, persistence failure, and no partial store update.
- [ ] Add a feedback-card test proving failures keep old content visible and show an actionable error.
- [ ] Run focused Jest tests and record the expected failures.

## Task 2: Candidate validation and atomic commit

- [ ] Add pure validation helpers for relationship people and the aggregate candidate.
- [ ] Generate the same nonzero cardinality as the existing people collection (default three when absent).
- [ ] Pass feedback to every person generation request and pass already generated people to later requests.
- [ ] Reject missing names, duplicate names, missing role/relationship text, missing summary, and cardinality mismatch.
- [ ] PATCH `{ relationships: candidate }` to the existing game before the single client-store update.
- [ ] Ensure every provider/validation/persistence failure leaves the old store object untouched.

## Task 3: Visible error semantics

- [ ] Make `SettingFeedbackCard` catch regeneration failures, retain the existing content/editor input, and show a safe error.
- [ ] Clear stale errors when retrying, cancelling, or succeeding.
- [ ] Keep the success log/UI transition after the atomic commit only.
- [ ] Run focused hook/card/page tests and strict TypeScript GREEN.

## Task 4: Verification and PR

- [ ] Scan for generic relationship regeneration and unvalidated relationship writes.
- [ ] Run focused backend character API/creator tests and frontend suites.
- [ ] Run `git diff --check` and `./test.sh all`.
- [ ] Browser-smoke success and forced-failure flows, proving old data survives failure and a valid candidate replaces it once.
- [ ] Audit the P1-5-only diff and prepare draft PR `fix(character): make relationship regeneration atomic`.
