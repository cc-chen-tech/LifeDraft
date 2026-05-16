## Context

The existing implementation has three important properties:

- It already has a working Netease recommendation path and a persistent per-game playlist.
- It currently treats AI analysis mostly as a keyword generator rather than a durable music intent model.
- Playlist merge behavior protects the currently playing song, but new recommendations can still replace the upcoming queue too aggressively for a smooth background-music experience.

The desired product direction is not "members always hear AI music first." It is:

```
All users:
  immediate Netease recommendations

Members:
  immediate Netease recommendations
  + background AI-generated instrumental/ambience tracks
  + generated tracks are inserted into future queue slots after completion
```

AI-generated music should feel like a premium supplement that gradually enriches the soundtrack, not a disruptive provider switch.

## Goals / Non-Goals

**Goals:**

- Improve story-to-music matching while keeping Netease as the fast baseline provider.
- Represent the story's music intent as structured data that can feed both search and future generation.
- Keep playback smooth: current song is never interrupted, and the next queued song remains stable where practical.
- Allow members to receive AI-generated instrumental/ambience tracks in the background queue after generation completes.
- Persist generated assets and generation metadata to avoid paying to regenerate equivalent music.
- Fall back to Netease when AI generation fails or is disabled.
- Keep the feature flag and membership gates explicit so unfinished generation providers do not affect non-member behavior.

**Non-Goals:**

- Replacing Netease as the primary provider.
- Building a full membership/billing system in this change.
- Implementing a specific AI music provider before provider selection is finalized.
- Auto-switching the currently playing song when a generated asset completes.
- Generating lyric songs by default. Generated tracks should default to instrumental/ambience loops.

## Proposed Architecture

```
Round/story context
        │
        ▼
MusicContextBuilder
        │
        ▼
MusicBrief
  mood, scene, era, pacing, energy
  instruments, search_queries
  negative_cues, generation_prompt
        │
        ├───────────────────────────┐
        ▼                           ▼
NeteaseMusicProvider          PremiumAiMusicJob
immediate recommendations     background generation
        │                           │
        ▼                           ▼
Netease result rerank         GeneratedMusicAsset
        │                           │
        └─────────────┬─────────────┘
                      ▼
             PlaylistQueuePolicy
             current song unchanged
             near-term queue stable
```

## Decisions

1. Netease remains the immediate provider.

   Every recommendation request should be able to return quickly through the Netease path. This keeps music available for non-members and prevents AI generation latency from blocking gameplay.

2. AI-generated music is a member-only background supplement.

   When the user is a member and the AI music feature flag is enabled, the system may enqueue a background generation job using the same `MusicBrief`. Completion updates future queue slots only.

3. Generated music defaults to instrumental/ambience loops.

   Background music should support reading and gameplay instead of competing with story text. Lyric or vocal songs can be a future explicit mode for special moments such as endings or character themes.

4. Queue updates should be gentle.

   The current song MUST remain unchanged. The first upcoming queue item SHOULD remain unchanged when there is already a near-term song. New generated tracks should be inserted after the near-term stable position, commonly at queue index 1 or 2, unless the user explicitly requests stronger AI mixing.

5. Generated assets are persisted outside the playlist.

   The playlist should reference music items, while generated audio metadata and file storage live in a reusable asset model. The database should store prompt/brief/provider/status metadata; the audio bytes should live in local file storage or object storage.

6. Reuse should be semantic, not only exact text hash.

   Cache keys should include `game_id` or world/style identifiers, `MusicBrief` hash, provider/model/version, and generation settings. Exact story text can be recorded for traceability, but tiny prose edits should not always force a new paid generation if the brief is equivalent.

7. Fallback is Netease, not silence.

   If a premium AI generation job fails, times out, or is disabled, the system should keep or refresh Netease recommendations and record the generation failure for diagnostics.

## Data Model Sketch

Potential generated asset metadata:

```text
GeneratedMusicAsset
  asset_id
  game_id
  source = "ai_generated"
  provider
  model
  status
  music_brief_json
  prompt_text
  brief_hash
  storage_path
  duration_ms
  loopable
  created_at
  updated_at
  error_message
```

Potential playlist item source metadata:

```text
MusicItem
  id
  source = "netease" | "ai_generated"
  name
  artists
  album
  duration
  url
  asset_id?
  provider?
  mood?
  keywords?
```

## Risks / Trade-offs

- **Better Netease matching may still be limited by the external catalog** -> Treat the music brief as the stable interface so future generation can improve quality without rewriting recommendation logic.
- **Background generation can complete after the scene has moved on** -> Insert generated tracks into the queue only if they still match the current or recent music brief, or keep them as reusable assets without immediate insertion.
- **Generated assets can increase storage and cost** -> Deduplicate by brief/provider hash and persist provider metadata for reuse.
- **Membership status may be unavailable in some API contexts** -> Default to Netease-only behavior unless membership and feature flag are explicitly true.
- **Queue insertion can feel surprising if too aggressive** -> Preserve current song and near-term queue, and add tests for queue stability.
