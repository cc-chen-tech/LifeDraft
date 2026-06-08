## 1. Test Gate Wiring

- [x] 1.1 Add new contract, DB, static/import, and E2E regression test files to the appropriate `test.sh` layers before implementation.
- [x] 1.2 Run the newly wired targeted tests and record the expected RED failures without editing those tests afterward.

## 2. Preset Relationship Authority

- [x] 2.1 Add contract tests for required-cast prompt text, cast coverage validation, and invented substitute detection.
- [x] 2.2 Add real DB integration coverage proving preset key people survive game create -> save -> read.
- [x] 2.3 Implement authoritative required-cast extraction and prompt/WorldModel constraint injection.
- [x] 2.4 Implement deterministic cast drift validation with retry guidance for missing preset people.
- [x] 2.5 Implement canonical key-person preservation in collection/entity synchronization.

## 3. Music Recommendation Quality

- [x] 3.1 Add contract tests for negative cue variant filtering and same-song different-ID dedupe.
- [x] 3.2 Add contract/API tests for `/api/music/generate` structured JSON degradation on MiniMax timeout/provider errors.
- [x] 3.3 Implement normalized negative cue matching and song identity dedupe in the music pool.
- [x] 3.4 Implement bounded MiniMax generation failure handling without blocking NetEase recommendation or story controls.

## 4. Currency Resource Consistency

- [x] 4.1 Add contract and DB tests for configured wealth amount and currency metadata through game initialization.
- [x] 4.2 Add frontend/E2E coverage for displaying configured yuan wealth instead of generic `货币`.
- [x] 4.3 Implement initial wealth extraction from `character_settings.wealth` with safe fallback.
- [x] 4.4 Implement frontend wealth formatting from character currency metadata.

## 5. Gameplay Recovery Follow-up

- [x] 5.1 Add frontend unit/E2E regression coverage for stale polling becoming actionable after a bounded timeout.
- [x] 5.2 Implement stale polling timeout state that preserves partial story and exposes retry/recovery controls.

## 6. Verification

- [x] 6.1 Run targeted backend tests for the new contracts and DB integration.
- [x] 6.2 Run targeted frontend Jest and Playwright tests for music, wealth display, and stale polling recovery.
- [x] 6.3 Run `openspec validate fix-20260608-story-quality-music --strict`.
- [x] 6.4 Run `./test.sh all` and fix only implementation code if tests fail.
