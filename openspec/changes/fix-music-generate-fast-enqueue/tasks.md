## 1. Root Cause And Tests

- [x] 1.1 Reproduce the blocking route behavior with a contract test that fails if `/api/music/generate` calls synchronous MiniMax generation in real-provider mode.
- [x] 1.2 Confirm the test fails before implementation with HTTP 503 from the patched blocking generator.

## 2. Implementation

- [x] 2.1 Make `/api/music/generate` enqueue and return 202 by default, with explicit `sync=true` reserved for deterministic ready-track verification.
- [x] 2.2 Preserve missing-key and disabled-generation 503 responses.
- [x] 2.3 Preserve existing playlist insertion behavior for background generation.
- [x] 2.4 Route frontend story-complete AI music enqueue requests through `/api/music/generate` instead of the legacy `/api/music/generate-async` endpoint.

## 3. Verification

- [x] 3.1 Run the new fast-enqueue contract test.
- [x] 3.2 Run existing sync ready-track, playlist insertion, async enqueue, and failure-path music generation tests.
- [x] 3.3 Regenerate OpenAPI schema/types and verify no drift.
- [x] 3.4 Run strict OpenSpec validation for this change.
- [x] 3.5 Run frontend store and player tests that prove automatic story-complete AI music generation uses `/api/music/generate` and still inserts generated tracks into the future queue.
