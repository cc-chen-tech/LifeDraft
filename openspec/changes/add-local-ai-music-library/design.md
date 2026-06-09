## Context

The current MiniMax music path already persists ready tracks in `generated_music_assets` and reuses them for the same `game_id`, provider, model, brief hash, and generation settings. That protects against exact duplicate generation, but it is not a music library: a later story with a similar workplace, suspense, recovery, or reflective scene still goes straight to MiniMax unless the exact brief identity matches.

The app also has two important UX constraints:

- NetEase recommendations remain the immediate baseline and must not wait for local-library lookup or MiniMax generation.
- Generated AI tracks are inserted into future queue slots and must not interrupt the current song.

The library must improve reuse without leaking source story details. MiniMax prompts can contain compact summaries, so cross-game reuse must expose only sanitized music descriptors and current-scene track labels to the frontend.

## Goals / Non-Goals

**Goals:**

- Treat every ready MiniMax music asset as a reusable local-library candidate.
- Look up suitable local AI tracks before making a new MiniMax generation call.
- Reuse tracks across games when the sanitized music profile is compatible and confidence is high.
- Preserve the current NetEase-first, future-queue insertion behavior.
- Record enough hit/miss/rejection metadata to tune matching quality.
- Reject stale assets whose audio file or generated URL is no longer playable.

**Non-Goals:**

- Replacing NetEase as the fast baseline music source.
- Building a public music-library browsing UI.
- Exposing another user's story summary, original prompt, game id, or private metadata to the frontend.
- Guaranteeing that every story gets a reused local track. Misses must still fall through to MiniMax generation or NetEase-only playback.
- Introducing vector-search infrastructure before simple scored metadata matching has proven insufficient.

## Decisions

### 1. Add a library service over generated music assets

Create a `LocalAiMusicLibraryService` or equivalent repository layer that indexes ready `GeneratedMusicAsset` rows into a searchable music profile. The first implementation can either extend `generated_music_assets` with additional columns or add a companion table keyed by `asset_id`; the service boundary should hide that storage choice.

Alternative considered: keep lookup inside `StoryMusicGenerationService.find_ready_asset`. That is too narrow because the current method intentionally matches only exact game/brief identity.

### 2. Use sanitized music profiles for matching and privacy

Library matching should use normalized fields such as mood, scene type, setting/environment, pacing, energy, instruments, negative cues, prompt version, duration, loopability, provider, model, and generation settings. The service may keep original `prompt_text` for internal diagnostics, but response objects and frontend track labels must be rebuilt from the requesting story's current brief.

Alternative considered: match on stored prompt text or story summary directly. That is simpler but risks privacy leakage and overfits prose differences rather than musical intent.

### 3. Lookup before MiniMax generation, after NetEase baseline

The recommendation flow still returns/persists NetEase songs immediately. The generation flow checks the local library first:

1. Build the current `MusicBrief`.
2. Search ready local AI assets with compatible provider/model/settings and playable audio.
3. Score candidates against the brief.
4. Reuse the best candidate when it clears a configured threshold and negative-cue checks.
5. Otherwise call MiniMax and index the newly ready asset.

Alternative considered: check the library before NetEase recommendation. That would risk delaying the first playable queue and does not improve the baseline UX.

### 4. Store reuse as an explicit event

When a library track is reused, record usage count, last used time, requesting game id, score, and decision reason. This can be a lightweight event table or structured logs plus counters, but tests should verify the observable metadata needed for tuning.

Alternative considered: silently return the track. That would make it hard to answer whether the library improves experience or causes mismatches.

### 5. Keep queue behavior unchanged

Reused library tracks should be converted to the same playlist-track shape as newly generated tracks, with `source="ai_generated"` and optional non-breaking metadata such as `library_reused=true`, `asset_id`, `provider`, `model`, and `brief_hash`. The playlist service still inserts them into future queue positions only.

Alternative considered: make reused local tracks current immediately because they are already ready. That would break the established no-interruption playback contract.

## Risks / Trade-offs

- Cross-story reuse can feel generic -> Require scene-fit thresholds, negative-cue rejection, and prompt/version compatibility before reuse.
- Stored prompt text can contain source-story details -> Use sanitized profiles for matching and frontend output; never expose source prompt/story metadata through playlist responses.
- Simple metadata scoring may miss near-matches -> Start with deterministic scoring and logs; add embeddings only if fixtures show persistent false negatives.
- Stale local files can create broken playback -> Verify audio availability before returning a library hit and fall back when unavailable.
- Global library reuse may not fit all privacy policies -> Keep a service-level scope option so deployments can choose global, per-user, or per-game reuse.

## Migration Plan

1. Add tests for library indexing, lookup-before-generation, stale file rejection, privacy-safe response fields, and future-queue insertion.
2. Add library metadata storage behind a repository/service boundary.
3. Backfill library profiles for existing ready `GeneratedMusicAsset` rows from `music_brief_json`.
4. Integrate local lookup into `StoryMusicGenerationService.generate_ready_track` before provider generation.
5. Add logging/counters for hit, miss, rejection, stale asset, and provider fallback reasons.
6. Deploy behind a feature flag such as `STORY_MUSIC_LOCAL_LIBRARY_ENABLED`; disabling the flag restores the existing MiniMax generation path.

## Open Questions

- The initial reuse scope should likely default to deployment-local/global with sanitized metadata, but implementation may choose per-user scope first if product privacy expectations require it.
- The first threshold can be conservative and fixture-driven; production telemetry should tune it after real usage.
- If future providers are added, provider/model compatibility should be explicit rather than assuming all generated assets are interchangeable.
