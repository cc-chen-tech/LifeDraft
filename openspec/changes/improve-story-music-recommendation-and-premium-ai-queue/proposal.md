## Why

The current music system analyzes story text into a small set of search keywords, searches Netease, filters unavailable URLs, and replaces the upcoming playlist with the remaining playable songs. This keeps music available, but matching quality is limited because rich narrative context is compressed into broad search terms. The result can feel detached from the scene, especially when the story has a clear era, mood, location, pacing, or dramatic turn.

AI-generated music is desirable for members, but it should not become the immediate primary path yet. Generated audio is slower, costlier, and needs persistence, provider fallback, and queue behavior that does not interrupt the current listening experience. The near-term goal is to improve the Netease baseline for everyone while preparing a premium AI-generated music supplement that can enter the background queue after generation completes.

## What Changes

- Introduce a structured `MusicBrief` concept that captures story mood, scene type, era, pacing, energy, instruments, search queries, negative cues, and a future generation prompt.
- Keep Netease as the immediate baseline music provider for all users.
- Improve Netease matching by building better search queries from the music brief and reranking search results before queue merge.
- Preserve smooth playback by never interrupting the current song and by keeping the near-term queue stable when new recommendations arrive.
- Add a premium-only AI music generation path as a background queue supplement, not as a replacement for Netease recommendations.
- Persist generated music assets and metadata so generated tracks can be reused instead of regenerated for the same or semantically equivalent scene.
- Fall back to Netease recommendations when AI generation fails, times out, or is unavailable.
- Add source metadata to music items so the frontend and backend can distinguish Netease tracks from AI-generated tracks.

## Capabilities

### New Capabilities

- `story-music-recommendation`: Story-aware music brief generation, Netease matching, smooth playlist queue updates, and premium AI-generated queue supplementation.

### Modified Capabilities

- None.

## Impact

- Backend music services: `src/services/music_service.py`, `src/services/music_playlist_service.py`, and any new provider/brief/job helpers.
- Backend music API: `src/api/routers/music.py` response schemas and playlist update behavior.
- Database models and migrations/init compatibility: generated music asset metadata, source metadata, and optional generation job state.
- Frontend music state and components: `useMusicStore`, `GlobalMusicPlayer`, `MusicPlayer`, and queue rendering/source display if surfaced.
- Tests: contract tests for music brief, provider selection, queue merge policy, premium gating, fallback behavior, generated asset reuse, and API response compatibility.
