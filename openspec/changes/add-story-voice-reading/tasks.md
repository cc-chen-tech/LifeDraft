## 1. Test Gate Scaffolding

- [x] 1.1 Add story voice reading strict mypy targets and static gate tests for typed schemas, service interfaces, and missing attributes before implementation code.
- [x] 1.2 Add import validation tests covering delayed imports for voice reading routers, services, providers, repositories, and frontend-facing schema modules before implementation code.
- [x] 1.3 Add producer/consumer contract tests for voice settings, reading context, job status, audio asset fields, and error response fields before implementation code.
- [x] 1.4 Add real DB integration tests for voice settings, reading jobs, generated audio metadata, text-hash reuse, and save-read recovery before implementation code.
- [x] 1.5 Add browser E2E tests for current-story reading, historical-round reading, auto-read state, retry failure state, and music coordination before implementation code.
- [x] 1.6 Wire every new story voice reading test into the appropriate `test.sh` layer before production implementation starts.
- [x] 1.7 Confirm the new tests fail for missing implementation and then treat them as locked: no skipping, no mocking, no deletion, and no weakening during implementation.

## 2. Backend Contracts and Persistence

- [x] 2.1 Add typed backend schemas for `ReadingContext`, voice settings, reading job status, generated audio metadata, and stable error responses.
- [x] 2.2 Add database models or migration/init support for persisted voice settings, reading jobs, and generated reading audio assets.
- [x] 2.3 Implement repositories for settings, reading jobs, generated assets, text-hash lookup, and job recovery using real DB sessions.
- [x] 2.4 Add feature flags and configuration for story voice reading, built-in voices, custom voice availability, provider selection, and local deterministic provider mode.
- [x] 2.5 Run and pass the story voice reading static, import, contract, and DB gate tests added in section 1.

## 3. Backend Reading Services and API

- [x] 3.1 Implement reading-context validation so current, historical, summary, and ending reads never infer the latest story incorrectly.
- [x] 3.2 Implement voice settings read/update endpoints with authenticated session behavior and stable field names.
- [x] 3.3 Implement reading request endpoints that return cached audio assets, create pending jobs, or return stable failure states.
- [x] 3.4 Implement deterministic local TTS provider behavior for tests and provider abstraction for future production TTS.
- [x] 3.5 Implement custom voice consent and membership gates without enabling unsafe custom synthesis by default.
- [x] 3.6 Run and pass backend story voice reading contract and real DB tests through `test.sh`.

## 4. Frontend State, Controls, and Audio Coordination

- [x] 4.1 Add frontend API client methods and generated or manually maintained types for voice settings, reading context, reading jobs, assets, and errors.
- [x] 4.2 Add a story voice reading store or hook for reading state, queue state, current source identity, playback controls, and recovery after reload.
- [x] 4.3 Add current story, history, summary, and ending reading controls using the existing gameplay UI patterns.
- [x] 4.4 Implement auto-read queue behavior that waits for completed visible story attempts and supersedes stale regenerated attempts.
- [x] 4.5 Implement music duck/pause/restore coordination while preserving manual user music changes.
- [x] 4.6 Run and pass frontend typecheck, component tests, and browser E2E tests for story voice reading through `test.sh`.

## 5. Final Verification

- [x] 5.1 Run `openspec validate add-story-voice-reading --strict` and fix only production/spec issues, not by weakening tests.
- [x] 5.2 Run `./test.sh all` and confirm strict mypy, import validation, contract tests, real DB integration, and browser E2E all pass.
- [x] 5.3 Manually verify in browser-agent that reading current story, reading historical story, auto-read, failure retry state, and music coordination match the specs.
- [x] 5.4 Document provider, feature flag, and custom voice limitations in the implementation summary before merge or PR.
