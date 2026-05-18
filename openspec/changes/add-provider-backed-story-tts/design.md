## Overview

Provider-backed story TTS keeps the current browser-speech fallback but adds a backend narration path that can be switched to a real TTS model provider. The backend owns synthesis provider selection, asset persistence, and generated audio URLs; the frontend owns deciding whether to play the returned audio asset or use browser `speechSynthesis` for immediate local availability.

## Goals

- Generate or reuse story narration assets through a typed backend provider interface.
- Expose provider metadata in settings and reading responses so the frontend does not confuse a local tone fixture with real narration.
- Support OpenAI-compatible speech synthesis with environment configuration while keeping tests offline and deterministic.
- Preserve existing reading context validation, text hash checks, queue semantics, and music ducking behavior.
- Verify browser-observable playback through audio element state for backend audio and speech synthesis state for browser fallback.

## Non-Goals

- Voice cloning, user-uploaded samples, or premium membership enforcement.
- Streaming audio generation.
- CI calls to paid external TTS providers.
- Guaranteeing that physical speakers emit sound; verification remains browser/runtime observable.

## Provider Model

The backend uses a `StoryTTSProvider` protocol returning `GeneratedSpeech`. The provider result includes storage path, duration, provider id, model id, MIME type, and playback mode.

Provider modes:

- `browser`: no backend audio asset is returned; the frontend uses `speechSynthesis` with the supplied story text.
- `local`: deterministic local WAV provider used for development and CI. It proves decode/playback and persistence without pretending to be real narration.
- `openai`: OpenAI-compatible speech provider configured by environment variables. It creates a WAV file from story text and stores it under a local generated voice asset directory.

The frontend only plays an `<audio>` asset when `playback_mode === "audio"` and `audio_url` is present. Otherwise it uses browser speech and records that state for E2E inspection.

## Configuration

Environment variables:

- `STORY_TTS_PROVIDER`: `browser`, `local`, or `openai`; default `browser`.
- `STORY_TTS_OPENAI_API_KEY`: optional provider-specific key; falls back to `OPENAI_API_KEY` when unset.
- `STORY_TTS_OPENAI_BASE_URL`: default `https://api.openai.com/v1`.
- `STORY_TTS_OPENAI_MODEL`: default `gpt-4o-mini-tts`.
- `STORY_TTS_ASSET_DIR`: generated WAV storage directory; default `data/voice_assets`.

When the selected provider is unavailable, the backend returns a browser fallback response rather than a local tone unless explicitly configured for `local`.

## Testing Strategy

Tests are written before implementation and wired into `test.sh` before production code is changed.

- Static analysis: strict mypy covers provider protocol, concrete providers, and service wiring.
- Import validation: delayed imports for provider factory and concrete providers are reachable.
- Contract tests: backend schemas and frontend TypeScript types share provider/playback fields.
- Real DB integration: provider-backed requests save assets and jobs, then reuse assets by text hash, voice, speed, provider, and model.
- E2E browser: verifies backend audio mode returns a decodable WAV audio element, and browser fallback mode uses `speechSynthesis` with the real story text instead of a WAV tone.

No tests are skipped and no mocks are used. Offline tests use real local provider implementations.

## Risks

- External TTS provider API behavior can drift. The implementation isolates the provider behind a small interface and keeps the default safe fallback browser-based.
- Generated audio files may accumulate locally. This change stores files by content hash/provider/model so repeated reads reuse existing assets.
- Browser autoplay can be policy-sensitive. E2E verifies the browser-observable playback/speech state instead of physical speaker output.
