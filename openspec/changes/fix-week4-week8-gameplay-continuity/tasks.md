## 1. Restore Committed Story Authority

- [x] 1.1 Add a regression test for an empty-ledger legacy save containing completed
  bookcase-purchase and public-event rounds.
- [x] 1.2 Reconstruct an idempotent continuity timeline from durable round history and
  render both exact choice and summary in prompt constraints.
- [x] 1.3 Run the focused continuity regression tests and commit the ledger fix.

## 2. Make Choice Generation Atomic

- [x] 2.1 Add failing tests proving standard and custom choice failures preserve the
  current event, resources, wealth ledger, histories, and round index.
- [x] 2.2 Replace fabricated continuation/custom-effect fallbacks with typed retryable
  errors and stage all choice mutations on a deep working state before commit.
- [x] 2.3 Reject contextual fallback option sets that duplicate recent committed choices.
- [x] 2.4 Run focused story, choice, and SSE tests and commit the atomic-choice fix.

## 3. Bound Life Summary and Media Context

- [x] 3.1 Add API tests for a provider timeout returning an evidence-only summary
  without gameplay mutation.
- [x] 3.2 Add frontend tests for client timeout clearing loading and displaying a
  retryable summary error.
- [x] 3.3 Implement bounded server/client deadlines and preserve valid media context
  when a choice result is rejected.
- [x] 3.4 Run focused backend/frontend tests, strict OpenSpec validation, and commit
  the summary-recovery fix.

## 4. Final Verification and Delivery

- [x] 4.1 Review the complete diff for unrelated changes, state-mutation ordering,
  migration idempotency, and CI compatibility.
- [x] 4.2 Run static/type checks, `openspec validate fix-week4-week8-gameplay-continuity --strict`,
  targeted tests, and the complete local test suite.
- [x] 4.3 Run browser/E2E recovery coverage, open a PR, and observe all PR checks.
