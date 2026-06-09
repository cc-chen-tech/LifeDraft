## 1. Tests First

- [ ] 1.1 Add contract tests proving ready generated music assets are indexed as local-library entries and non-ready assets are excluded.
- [ ] 1.2 Add real DB tests for cross-game library lookup by sanitized music profile, provider/model/settings compatibility, and usage metadata updates.
- [ ] 1.3 Add provider-boundary tests proving a high-confidence local-library hit avoids a MiniMax generation call.
- [ ] 1.4 Add rejection tests for negative-cue conflicts, low scene-fit score, stale/missing audio, and provider/model mismatch.
- [ ] 1.5 Add playlist/store tests proving reused local AI tracks enter future queue without interrupting current playback.
- [ ] 1.6 Add API/privacy tests proving reused tracks do not expose source game id, original prompt text, story summary, or source story details.
- [ ] 1.7 Run the new targeted tests before implementation and confirm they fail for the missing library behavior.

## 2. Data Model And Repository

- [ ] 2.1 Add a local AI music library storage shape by extending `generated_music_assets` metadata or adding a companion table keyed by `asset_id`.
- [ ] 2.2 Add indexes for lookup fields such as status, provider, model, scene type, mood, energy, instruments/tags, loopability, and updated time where supported by the DB.
- [ ] 2.3 Implement a repository that can upsert a sanitized library profile for a ready generated asset.
- [ ] 2.4 Implement a backfill path that creates library profiles for existing ready generated music assets from `music_brief_json`.
- [ ] 2.5 Add stale-audio checks that reject library rows whose local file or generated endpoint is not playable.

## 3. Library Matching Service

- [ ] 3.1 Implement sanitized music-profile normalization from `MusicBrief` and stored asset metadata.
- [ ] 3.2 Implement deterministic library candidate scoring for mood, scene type, environment, pacing, energy, instruments, negative cues, duration, and loopability.
- [ ] 3.3 Add configurable match thresholds, lookup timeout, reuse scope, and a feature flag such as `STORY_MUSIC_LOCAL_LIBRARY_ENABLED`.
- [ ] 3.4 Return structured match decisions with selected asset, score, hit/miss status, and rejection reasons.
- [ ] 3.5 Record usage count, last-used time, requesting game id, score, and reason when a library track is reused.

## 4. Generation Flow Integration

- [ ] 4.1 Integrate local-library lookup into `StoryMusicGenerationService.generate_ready_track` before provider generation.
- [ ] 4.2 Convert reused library assets to the existing generated-track playlist shape with compatible fields and optional non-breaking reuse metadata.
- [ ] 4.3 Ensure `/api/music/generate` and `/api/music/generate-async` both reuse high-confidence local tracks and still fall back to MiniMax on misses.
- [ ] 4.4 Index newly generated MiniMax assets immediately after they become ready.
- [ ] 4.5 Ensure local-library lookup failures degrade to the existing NetEase/MiniMax path without blocking story continuation.

## 5. Frontend And API Compatibility

- [ ] 5.1 Preserve generated-track fields and unknown reuse metadata in frontend music store state.
- [ ] 5.2 Verify `MusicPlayer` and queue polling treat reused local AI tracks the same as newly generated tracks.
- [ ] 5.3 Keep existing API response fields backward compatible for current music recommendation and playlist consumers.

## 6. Verification

- [ ] 6.1 Run targeted backend contract and DB tests for local AI music library behavior.
- [ ] 6.2 Run targeted frontend music store/player tests.
- [ ] 6.3 Run `openspec validate add-local-ai-music-library --strict`.
- [ ] 6.4 Run the relevant `./test.sh` layers for the touched backend, DB, contract, frontend, and E2E music behavior before implementation is marked complete.
