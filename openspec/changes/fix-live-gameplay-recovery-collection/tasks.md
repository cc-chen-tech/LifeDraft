## 1. Tests First

- [x] Add backend regression tests for generation timeout/recoverable `/play` state.
- [x] Add frontend or contract test proving recovery controls remain visible until playable content returns.
- [x] Add auth contract tests for `private_id` login payload and specific error messaging.
- [x] Add character continuity tests proving structured creation settings are present in opening/round generation prompts or inputs.
- [x] Add collection recognition tests for metadata-gated character candidates, duplicate suppression, and terminal empty/error state.
- [x] Add media tests for HTTPS-safe music URLs and non-blocking media failures.
- [x] Add regression test for friend request timestamps returned as database `datetime` values.
- [x] Add preflight regression coverage for Python 3.9 API router import compatibility.
- [x] Add frontend recovery regression test proving stuck generation refs are cleared before retry.
- [x] Promote collection store error-message regression coverage into the local preflight gate.
- [x] Add and promote create-page long-running generation guidance coverage.

## 2. Implementation

- [x] Fix generation/retry persistence so timeout states are recoverable after refresh and direct `/play`.
- [x] Fix play-page recovery UI so it never collapses to a bare `故事生成中...` state after recovery is requested.
- [x] Align private-id login payloads and user-facing login errors.
- [x] Thread canonical character settings into opening and round generation, and add premise-drift guardrails.
- [x] Fix collection smart recognition to gate character candidates by system relationship/importance metadata, suppress duplicates, and terminally handle empty/error/loading states.
- [x] Normalize/proxy music URLs and degrade music/image failures without blocking story progress.
- [x] Serialize friend request timestamps at the API boundary to avoid 500s during pending-request listing.
- [x] Keep API router runtime annotations compatible with the Python 3.9 E2E backend launcher.
- [x] Wire `/play` recovery to a forced abort/reset/retry path instead of ordinary guarded generation.
- [x] Show a clear long-running generation hint during slow character creation instead of appearing stuck.

## 3. Verification

- [x] Run targeted backend tests added in this change.
- [x] Run targeted frontend tests added in this change.
- [x] Run minimal browser/e2e recovery flow locally.
- [x] Run OpenSpec validation for this change.
- [x] Before PR: run the agreed broader local gate set.
- [x] Perform code review before commit/PR.
- [ ] Push branch and create PR only after local validation passes.
- [ ] Merge to `main` only after PR checks are green, then verify deployment/live story101.live recovery flow.
