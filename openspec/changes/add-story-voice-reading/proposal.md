## Why

Story2 already treats narrative text, history review, scene images, and music as first-class parts of gameplay, but story voice reading is only captured as a thin member-feature placeholder. A real reading capability needs explicit contracts for what text is read, how reading follows story generation and history selection, and how voice playback coexists with background music.

## What Changes

- Add a dedicated story voice reading capability for current story text, historical rounds, summaries, and ending text.
- Define explicit reading context keys so voice playback cannot accidentally read the latest story while the user is reviewing history.
- Add selectable built-in voice settings, auto-read behavior, and a staged path for member-only custom voice upload or synthesis.
- Add a reading queue that follows generation-attempt boundaries, replaces stale regenerated text, and preserves story order.
- Coordinate voice playback with existing music playback so full-volume background music does not compete with narration.
- Require test-first implementation for every feature and bug fix in this change: static analysis, import validation, contract tests, real DB integration, and browser E2E coverage must be written before production code, wired into `test.sh`, not skipped, and not mocked.

## Capabilities

### New Capabilities

- `story-voice-reading`: Voice reading for visible story content, history review, summaries, settings, playback queue behavior, audio coordination, persistence, and required test gates.

### Modified Capabilities

- `story-music-recommendation`: Voice playback changes how background music should duck, pause, and restore while narration is active.

## Impact

- Frontend gameplay UI: play page, streaming story display, history drawer, summary/ending views, and controls for reading state.
- Frontend audio state: existing music player/store coordination with voice playback and user-initiated music changes.
- Frontend API types and client methods for voice reading settings, synthesis requests, queue status, and generated audio assets.
- Backend API routes and schemas for reading context validation, voice settings, synthesis job lifecycle, and audio asset lookup.
- Backend persistence for reading settings, reading jobs, generated audio asset metadata, and text-hash based reuse.
- TTS provider integration behind a feature flag with deterministic fallbacks for local and test environments.
- Test orchestration in `test.sh` across strict mypy, import validation, producer/consumer contract tests, real DB save-read integration, and no-mock browser E2E coverage.
