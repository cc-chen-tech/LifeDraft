## Why

Story voice reading currently has two incomplete paths: browser speech can read story text, while the backend asset API still represents narration with a deterministic WAV tone. Users need a provider-backed narration contract so "read story" can graduate from browser-only speech to real synthesized audio without regressing local verification or CI.

## What Changes

- Add a provider-backed story TTS capability with explicit provider modes: browser fallback, deterministic local provider, and OpenAI-compatible speech provider.
- Extend story voice reading responses and settings with playback mode and provider metadata so the frontend can choose backend audio only when real audio is available.
- Keep local and CI verification deterministic by using a no-network provider that returns valid WAV bytes through the same persistence and playback path.
- Add no-mock tests across strict mypy targets, import reachability, producer/consumer contracts, real DB save-read, and browser E2E playback state.
- Update `test.sh` so all new story TTS tests run through the existing layered gates before implementation is considered complete.

## Capabilities

### New Capabilities
- `provider-backed-story-tts`: Provider-backed story narration, provider availability, audio asset metadata, frontend playback selection, and no-mock test gates.

### Modified Capabilities
- None. The change builds on the existing story voice reading implementation and documents the provider-backed extension as a new capability.

## Impact

- Backend story voice reading service, router, schemas, repository usage, and configuration.
- Frontend story voice store, API types, and story voice controls.
- Story voice contract, import, real DB, strict mypy, and Playwright E2E tests.
- `test.sh` layer membership for the new test files and OpenSpec strict validation.
