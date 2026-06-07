## Context

The app already has two useful foundations:

- Story voice reading has a provider interface, persisted voice assets/jobs, settings, and frontend controls that understand `audio` versus `browser_speech` playback.
- Music already has a fast NetEase recommendation path, a persistent per-game playlist, and a queue policy that can insert generated tracks without replacing the current track.

MiniMax adds two external generation paths:

- Async TTS over HTTP, which creates a synthesis task, polls for completion, and downloads the resulting file. This is a better fit for complete story narration and long text than the previous deterministic local tone.
- Music generation over HTTP, which can create story-conditioned background music from a compact prompt/brief and return generated media.

The user-facing defaults are intentionally asymmetric: story auto-reading defaults off, while AI music generation defaults on. Reading can be distracting and should remain a user choice; generated background music improves the default story experience but must not block story progress or run without cost controls.

## Goals / Non-Goals

**Goals:**

- Add `minimax` as a configured story TTS provider that returns real playable audio assets.
- Keep browser speech as the fallback when MiniMax is unavailable, disabled, or fails.
- Trigger provider-backed story reading only after story text generation is complete and only when the user has enabled auto-read or explicitly clicks read.
- Generate instrumental MiniMax music after story completion by default, using a compressed music brief rather than raw unbounded story text.
- Insert generated music into the future playlist queue without interrupting current playback.
- Persist generated asset identity, provider/model/settings, prompt/brief hash, status, and error metadata for reuse and diagnostics.
- Make the feature test-first across static, import, contract, real DB, and browser E2E layers, all reachable from `test.sh`.

**Non-Goals:**

- Replacing NetEase recommendations as the fast baseline music provider.
- Generating lyric songs by default.
- Using a committed API key or calling paid MiniMax endpoints in normal local/CI test gates.
- Making speaker output a CI gate. Browser automation verifies decodable audio and playback state, not physical sound output.
- Reworking the membership/billing system.

## Decisions

### 1. Put MiniMax behind provider adapters

`MiniMaxTTSProvider` and `MiniMaxMusicGenerationProvider` will map app-level request objects into MiniMax API payloads. Business services will not build MiniMax-specific JSON or task-polling requests directly.

Alternative considered: call MiniMax directly from story/music services. That is faster to write but spreads provider fields through business logic and makes future model/provider changes harder.

### 2. TTS uses async provider audio first, with browser speech fallback

When `STORY_TTS_PROVIDER=minimax` and credentials are present, story reading will synthesize to a persisted audio file and return `playback_mode=audio`. If MiniMax is not configured or synthesis fails, the response remains truthful: `playback_mode=browser_speech`, no fake WAV/tone URL, and the frontend reads `context.text` with browser speech.

Ready narration assets are reused only within the requesting user's asset set. Equivalent text/voice/speed/provider/model requests from another user must generate or reuse that user's own asset instead of attaching a job to someone else's stored narration file.

Alternative considered: use MiniMax WebSocket TTS as the primary path. It can be lower latency for short snippets, but async TTS better matches complete generated stories, has clearer long-text semantics, and avoids requiring WebSocket runtime dependencies for normal story reading.

### 3. Auto-read remains opt-in

The settings default for `auto_read_enabled` remains false unless `STORY_TTS_AUTO_READ_DEFAULT_ENABLED` is explicitly enabled for the deployment. The completion hook only starts TTS automatically when settings report auto-read enabled; manual read still works from the voice controls.

Alternative considered: auto-read on by default. That improves discoverability but can be intrusive, expensive, and surprising for users in public/noisy environments.

### 4. Music generation defaults on but is non-blocking and bounded

After story completion, the music orchestration path builds a `MusicBrief`, returns/keeps NetEase recommendations immediately, and schedules MiniMax instrumental generation in the background when enabled. The NetEase baseline queue is persisted through the playlist API before MiniMax generation, and generated tracks are inserted into the persisted playlist only in future queue positions. The frontend still inserts the returned track into its live store so the current session updates immediately, then can restore the same queue from `/api/music/playlist/{game_id}` after navigation or reload.

Cost and latency bounds:

- A feature flag can disable AI music globally.
- A per-game/story brief hash avoids regenerating equivalent music.
- Timeouts and failure statuses prevent stuck jobs from blocking the UI.
- Generated assets are reused when provider/model/settings/brief identity matches.

Alternative considered: block music response until generated audio is ready. That would make the first playback slow and fragile.

### 5. Use compact briefs, not raw story dumps, for music prompts

Music generation receives a bounded brief with mood, scene, tempo, instrumentation, intensity, and negative cues. The brief may include a short story summary, but not the entire story text.

Alternative considered: pass the full story text directly. That risks prompt length issues, cost, unstable outputs, and leaking irrelevant prose into music generation.

### 6. Tests use real local boundaries, not mocks

Provider contract tests can run against local in-process HTTP servers that emit deterministic MiniMax-shaped responses. Legacy WebSocket compatibility can remain covered separately if used. This keeps tests offline and repeatable while still validating serialization, task polling, asset saving, and error handling across real IO boundaries.

Alternative considered: monkeypatch provider methods. That would be faster but would not catch broken payload fields, delayed imports, or real save/read integration.

## Risks / Trade-offs

- MiniMax API schema drift -> Keep provider contract tests focused on documented request/response fields and isolate schema mapping in adapter modules.
- Paid API misuse -> Never require a real key in tests; require env-driven configuration and add preflight checks that no secrets are committed.
- Long story text exceeds direct async text limits -> Fall back to browser speech with a clear status; future work can add MiniMax text-file upload for very long stories.
- Music generation completes after the story has moved on -> Persist the asset and insert only if the playlist still belongs to the same game and matching brief context.
- Generated music may conflict with narration -> Default to instrumental/background prompts and keep vocal/lyric generation out of scope.
- Browser autoplay policies -> E2E tests trigger playback through user-like interaction and assert `HTMLAudioElement` state after a decodable audio URL is attached.

## Migration Plan

1. Add OpenSpec and tests first.
2. Add provider/config/import surfaces without enabling external calls by default.
3. Add persistence and DB migrations for any new generated music metadata.
4. Add MiniMax TTS provider and story-reading service integration.
5. Add MiniMax music provider, brief builder, background generation orchestration, and playlist insertion.
6. Add frontend status/queue handling and browser E2E coverage.
7. Deploy with MiniMax env vars only on the target host. If production issues appear, set the feature flags to browser TTS fallback and NetEase-only music without rolling back the whole release.

## Open Questions

- Exact production model defaults may be adjusted after cost/latency testing. Initial implementation should default to latency-conscious TTS and `music-2.6` for music unless MiniMax account limits require another model.
- If MiniMax requires account-specific group identifiers for some endpoints, they must be configured through env vars beside `MINIMAX_API_KEY`.
