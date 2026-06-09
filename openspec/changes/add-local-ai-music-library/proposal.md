## Why

MiniMax-generated tracks are currently persisted only as reusable generation assets for equivalent game/brief/provider identity. That prevents duplicate generation for the same exact context, but it does not turn successful generations into a searchable local soundtrack that can improve later stories before spending another MiniMax call.

## What Changes

- Add a local AI music library layer over ready generated music assets.
- Extract and persist searchable library metadata from each generated track, including normalized mood, scene type, environment, pacing, energy, instruments, negative cues, prompt fingerprint, provider/model/settings, duration, loopability, and optional quality/use counters.
- Query the local library before starting MiniMax generation and return matching local AI tracks as future-queue candidates when confidence is high enough.
- Keep NetEase as the immediate baseline queue and keep MiniMax generation as the fallback when the local library has no suitable match.
- Prevent unsuitable reuse by enforcing negative cues, provider/model compatibility, audio availability, and scene-similarity thresholds.
- Add observability for library hit/miss/rejected reasons so matching behavior can be tuned without guessing.

## Capabilities

### New Capabilities
- `local-ai-music-library`: Persisted AI-generated tracks become a local, searchable music library that can be queried before new MiniMax generation.

### Modified Capabilities
- `music-and-media-degradation`: Local library lookup failures must degrade to the existing NetEase/MiniMax flow without blocking story playback.

## Impact

- Backend services:
  - `src/services/minimax_music_generation.py`
  - `src/services/music_service.py`
  - `src/services/music_playlist_service.py`
  - new or extended repository/service modules for generated music library indexing and lookup
- API:
  - `/api/music/generate` and `/api/music/generate-async` may reuse a local generated track before calling MiniMax.
  - Optional diagnostics can be added to generation responses or logs without breaking existing frontend fields.
- Data:
  - Extend `generated_music_assets` metadata or add a companion table/index for library lookup, similarity scoring, usage counters, and rejection diagnostics.
- Tests:
  - Contract tests for lookup-before-generation, cue filtering, queue insertion, and response compatibility.
  - Real DB tests for cross-game library reuse and stale/missing audio rejection.
  - Frontend store tests proving reused AI tracks still enter future queue without interrupting current playback.
