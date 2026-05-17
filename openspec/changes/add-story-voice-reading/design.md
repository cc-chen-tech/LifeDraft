## Context

Story2's gameplay screen already has several sources of narrative text: the current streamed story, round result text, history review text, generated summaries, and endings. The current frontend also has a persistent global music player mounted outside the play page, while story text and history state live inside play-page hooks and stores.

Voice reading needs to bridge those areas without reintroducing the earlier state-source ambiguity that caused history and media regressions. The system must always know which visible text is being read, which generation attempt produced it, and whether the text belongs to the current round or a selected historical round.

The repository already uses a strict test gate model through `test.sh`: mypy, import validation, contract tests, real DB integration, and browser E2E. This change adopts that as an implementation contract, not as optional cleanup after the feature is built.

## Goals / Non-Goals

**Goals:**

- Add manual voice reading for the visible current story, selected historical round, summary text, and ending text.
- Add auto-read mode that reads newly completed story content in order without reading stale regenerated attempts.
- Support built-in voice selection and persist per-user or per-session voice reading settings.
- Define a premium/custom voice path without requiring voice cloning in the MVP.
- Persist generated audio metadata and reuse audio by reading-context and text hash.
- Coordinate narration with background music so the two audio streams do not compete at full volume.
- Require test-first implementation with no skipped tests and no mocks; all new gate tests must be wired into `test.sh` before production code changes.

**Non-Goals:**

- Implementing a specific third-party TTS or voice-cloning provider before provider selection and privacy review are complete.
- Adding multi-character dramatized reading or per-speaker voice assignment.
- Adding offline downloads or long-form audiobook export.
- Replacing the existing music player or rewriting the full gameplay page layout.
- Weakening existing tests, skipping E2E coverage, or replacing real DB checks with mocked persistence.

## Decisions

1. Use explicit `ReadingContext` instead of raw text-only requests.

   A reading request should include `source_type`, `game_id`, `week`, `round_number`, `stage`, `attempt_id` where available, `text_hash`, and the text to read. This prevents the backend and frontend from guessing whether the user means the current round or a historical round.

   Alternative considered: send only `game_id` and let the backend load the latest state. That would recreate the history fallback problem and is not acceptable for historical reading.

2. Treat voice reading as a separate audio runtime coordinated with music.

   Voice narration should have its own playback state and queue, but it must call into a shared audio coordination layer to duck, pause, and restore music. This avoids coupling TTS loading to the existing music recommendation store while still protecting the user experience.

   Alternative considered: reuse the music queue for narration. That would blur two different domains: music tracks are background ambience, while narration is foreground content tied to exact text and progression.

3. Generate or fetch audio through a backend reading job API.

   The frontend should request reading audio by context. The backend can return a ready cached asset, create a pending job, or fall back to browser speech only if explicitly supported by product policy. Job metadata should be persisted so retries and reloads can recover state.

   Alternative considered: browser-only Web Speech API. It is fast for a prototype but gives weak voice control, poor cross-browser consistency, and little persistence. It may remain a fallback but not the main contract.

4. Cache generated audio by normalized text hash plus voice settings.

   The cache key should include normalized text hash, source identity, voice id, speed, provider, model/version, and language. Small UI reloads should not regenerate audio for identical text, while story regeneration with different text must produce a different asset.

   Alternative considered: cache only by story round. That fails when a round is regenerated or rewritten without changing week/round identity.

5. Auto-read only commits completed visible text.

   Streaming chunks can update the visual story, but auto-read should queue a segment only after the generation attempt reaches a stable completion boundary. If regeneration replaces the attempt, any queued or pending reading for the superseded attempt must be cancelled or marked obsolete.

   Alternative considered: read streaming chunks live. That creates duplicated narration on retries and awkward partial sentences; it can be revisited later as a separate "live narration" mode.

6. Custom uploaded voice is a gated future path.

   The MVP should support built-in voices and settings. Uploading voice material requires consent, ownership, safety checks, storage limits, deletion, and provider-specific processing, so the spec defines the gate but implementation can stage it after basic reading is stable.

7. Tests are immutable after being written for this change.

   Each task that changes behavior must start by adding failing tests in the appropriate layer. Once those tests are added and reviewed as valid, implementation work must adapt production code to pass them; the tests must not be skipped, mocked, weakened, or removed to make the feature pass.

## Risks / Trade-offs

- Provider latency can make reading feel slow -> Return cached assets immediately when available and expose pending job state with clear UI affordances.
- TTS provider failures can block a foreground feature -> Preserve a readable text UI, record job failure, and allow retry without blocking gameplay progression.
- Audio coordination can fight user intent -> Restore music only when the system ducked or paused it, not when the user manually paused or changed music.
- Storing generated audio can grow quickly -> Store metadata with retention policy hooks and reuse by hash; add cleanup as a follow-up if storage pressure appears.
- Uploaded/custom voice features have privacy and abuse risk -> Keep them behind membership, explicit consent, validation, deletion, and feature flags.
- Browser E2E can become flaky if it depends on external TTS -> E2E must use local deterministic provider configuration or preseeded real assets without mocking frontend or network behavior.

## Migration Plan

1. Add the new spec and tests without changing production behavior.
2. Add persistence for voice reading settings, jobs, and generated asset metadata with migrations/init compatibility.
3. Add backend routes and schemas behind a feature flag.
4. Add frontend API types, reading controls, and reading state store.
5. Add audio coordination with the existing music player.
6. Enable browser E2E coverage in `test.sh`.
7. Roll back by disabling the feature flag while leaving persisted metadata harmless and ignored.

## Open Questions

- Which TTS provider should be the first production provider?
- Is basic built-in voice reading available to all users, or only members?
- What are the exact retention and deletion requirements for generated reading audio?
- Should summaries and endings auto-read by default, or only support manual reading?
