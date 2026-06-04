## Why

Story reading currently improves only when the user manually starts browser speech or a configured backend audio provider exists. Music matching also remains catalog-bound: NetEase recommendations are fast, but they cannot always produce a track shaped to the generated story scene.

This change adds MiniMax-backed generated audio so completed stories can receive real provider narration when enabled, and AI-generated instrumental music can be added to the existing music queue after the story is complete.

## What Changes

- Add a MiniMax story TTS provider that can synthesize story text into a persisted playable audio asset.
- Default story auto-reading remains disabled; when the user enables auto-read, story completion triggers provider-backed reading when MiniMax is configured, with browser speech as fallback.
- Add MiniMax AI music generation that builds a compact music brief from story content and generates instrumental background music after story completion.
- Default AI music generation is enabled, but it must be feature-flagged, rate/cost bounded, and non-blocking for gameplay.
- Insert generated music into future playlist slots without interrupting the current track or destabilizing the near-term queue.
- Persist provider metadata, prompt/brief identity, generated asset metadata, and job status so equivalent requests can reuse existing assets.
- Wire layered tests through `test.sh` before implementation is considered complete: strict mypy targets, import validation, contracts, real DB integration, and browser E2E coverage.
- Do not commit API keys or secrets; MiniMax credentials are provided only through environment variables.

## Capabilities

### New Capabilities
- `minimax-story-audio-generation`: MiniMax-backed story narration and story-conditioned instrumental music generation, including provider contracts, persistence, queue insertion, defaults, and layered test gates.

### Modified Capabilities
- `provider-backed-story-tts`: Add MiniMax as a configured backend audio provider while preserving truthful browser-speech fallback semantics.
- `music-and-media-degradation`: Add provider-backed generated music as a non-blocking supplement that falls back to NetEase recommendations and never leaves the player silent.
- `test-gates`: Require the new MiniMax provider, persistence, contract, DB, and browser E2E tests to be reachable from `test.sh`.

## Impact

- Backend services: story TTS provider selection, MiniMax async HTTP TTS/music clients, music brief generation, music generation provider, asset persistence, playlist insertion, and story completion hooks.
- Backend APIs: voice-reading responses may include MiniMax provider metadata and audio asset URLs; music APIs may expose generated-track source metadata and generation job status.
- Database: generated narration/music asset metadata and job records may need new columns or tables, depending on existing model fit.
- Frontend: story voice controls, auto-read trigger behavior, music queue display, generated-track labels/status, and browser-agent verification hooks.
- Configuration: `MINIMAX_API_KEY`, MiniMax model/provider env vars, feature flags, timeout/rate-limit settings, and generated asset directories.
- Tests: new or updated Python unit/contract/DB/import/mypy tests, frontend store/component tests, Playwright/browser E2E tests, and `test.sh` wiring.
