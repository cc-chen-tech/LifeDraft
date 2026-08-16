# Gapless Story Narration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace paragraph-by-paragraph media switching with one continuous MiniMax chapter asset while preserving paragraph highlighting, click-to-read, resume, and recovery.

**Architecture:** MiniMax synthesizes the complete chapter once and returns the audio bundle plus sentence subtitles. The backend maps subtitle timestamps to stable story paragraphs and exposes every paragraph as a cue into the same chapter audio URL. The frontend owns one `<audio>` element, seeks to cue boundaries, and derives the active paragraph from the chapter clock, so normal playback never changes media sources.

**Tech Stack:** FastAPI, SQLAlchemy, MiniMax async T2A, SRT subtitle parsing, React/TypeScript, Jest, Playwright.

**Spec:** User-reported production regression on 2026-08-16: every paragraph boundary pauses for 1-2 seconds even after adjacent-file preloading; retain high-quality MiniMax-only narration and paragraph click-to-read.

## Global Constraints

- Use only MiniMax high-quality audio; do not add browser speech fallback.
- Keep existing `/api/voice-reading/audio/{file_name}` Range transport.
- Keep progress identity and paragraph-local `position_ms` compatible.
- Old v2 assets and jobs remain stored but are not reused by the new cache namespace.
- Selecting a story choice must stop the chapter audio and prevent stale playback.

---

### Task 1: Parse a MiniMax chapter bundle and produce paragraph cues

**Files:**
- Modify: `src/services/story_tts_provider.py`
- Modify: `src/services/minimax_story_tts_provider.py`
- Test: `tests/test_minimax_tts_protocol_parser_contracts.py`
- Test: `tests/test_minimax_tts_fallback_contracts.py`

**Interfaces:**
- Produces: `ParagraphCue(paragraph_index: int, start_ms: int, end_ms: int)` and `GeneratedSpeech.paragraph_cues`.
- Consumes: `context["paragraphs"]` as the ordered stable paragraphs already used by the job.

- [ ] **Step 1: Write failing bundle-parser tests**

  Create an in-memory tar fixture containing `chapter.mp3`, sentence-level `chapter.srt`, and metadata JSON. Assert that extraction returns the audio bytes and maps the first subtitle of each literal paragraph to cue starts `0` and `1250`, with the final cue ending at the parsed audio duration.

- [ ] **Step 2: Run the parser tests and verify RED**

  Run: `pytest -q tests/test_minimax_tts_protocol_parser_contracts.py`
  Expected: FAIL because chapter subtitle extraction and `ParagraphCue` do not exist.

- [ ] **Step 3: Implement chapter bundle parsing**

  Parse SRT timestamps into ordered sentence cues, normalize only whitespace for text matching, align subtitle text monotonically against the exact ordered paragraphs, reject overlapping or decreasing cue times, and retain the existing audio-byte validation. Detect tar bundles even when the file endpoint returns `application/octet-stream`.

- [ ] **Step 4: Return cues from the provider**

  Send the complete chapter text in one async request, persist one atomic audio file, validate its real duration, and return paragraph cues with `end_ms` set to the next paragraph start or chapter duration. Local deterministic audio divides its known duration monotonically across the supplied paragraphs.

- [ ] **Step 5: Run provider tests and verify GREEN**

  Run: `pytest -q tests/test_minimax_tts_protocol_parser_contracts.py tests/test_minimax_tts_fallback_contracts.py tests/test_story_tts_provider_contracts.py`
  Expected: PASS.

### Task 2: Persist and expose one chapter asset with paragraph cue offsets

**Files:**
- Modify: `src/database/models.py`
- Modify: `src/services/story_voice_repository.py`
- Modify: `src/services/story_voice_reading.py`
- Modify: `src/api/schemas.py`
- Test: `tests/test_story_voice_reading_db.py`
- Test: `tests/test_story_voice_async_chapter.py`
- Test: `tests/test_story_voice_routes_v2.py`

**Interfaces:**
- Consumes: `GeneratedSpeech.paragraph_cues` from Task 1.
- Produces: segment JSON fields `start_ms` and `end_ms`; all ready segments share the chapter `audio_url` and `asset_id`.

- [ ] **Step 1: Write failing service and API tests**

  Assert one provider synthesis call receives the full story, every segment shares `/api/voice-reading/audio/chapter.mp3`, cue offsets are ordered, repeat requests reuse the v3 chapter asset, and a stale worker cannot publish cue or asset state after losing its lease.

- [ ] **Step 2: Run service tests and verify RED**

  Run: `pytest -q tests/test_story_voice_reading_db.py tests/test_story_voice_async_chapter.py tests/test_story_voice_routes_v2.py`
  Expected: FAIL because segment cue columns and chapter synthesis are absent.

- [ ] **Step 3: Add the idempotent cue migration**

  Add nullable integer `start_ms` and `end_ms` columns to `voice_reading_segments` and to `_ensure_legacy_columns()`. Increment `VOICE_ASSET_VERSION` to `3` so paragraph assets and jobs from v2 are retained but not reused.

- [ ] **Step 4: Publish the chapter atomically under the existing lease fence**

  Claim the job once, synthesize `job.context_json["text"]` with ordered segment text supplied as `paragraphs`, create one asset keyed by the chapter hash, assign the same asset plus cue offsets to all segments, and commit ready state only while the lease token still matches. On provider or alignment failure, fail the job without partial ready segments.

- [ ] **Step 5: Expose cue fields compatibly**

  Add optional `start_ms` and `end_ms` to `VoiceReadingSegmentResponse`; old rows continue to serialize with null cues, while v3 jobs always return non-null monotonic cues.

- [ ] **Step 6: Run service tests and verify GREEN**

  Run: `pytest -q tests/test_story_voice_reading_db.py tests/test_story_voice_async_chapter.py tests/test_story_voice_routes_v2.py tests/test_story_voice_reading_db_contracts.py`
  Expected: PASS.

### Task 3: Play one chapter media element and seek by paragraph cue

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/components/game/StoryListeningExperience.tsx`
- Test: `frontend/src/__tests__/components/StoryListeningExperience.test.tsx`

**Interfaces:**
- Consumes: shared `audio_url`, `start_ms`, and `end_ms` from Task 2.
- Produces: one stable audio element whose source never changes at normal paragraph boundaries.

- [ ] **Step 1: Write failing component tests**

  Assert that two ready paragraphs sharing one URL render exactly one `<audio>`, crossing the first cue boundary changes the highlighted paragraph without firing `pause`, `load`, or another `play`, clicking paragraph two seeks the same element to `start_ms`, resumed paragraph-local progress seeks to `start_ms + position_ms`, and selecting a choice pauses the element and invalidates pending playback.

- [ ] **Step 2: Run the component test and verify RED**

  Run: `npx jest src/__tests__/components/StoryListeningExperience.test.tsx --runInBand`
  Expected: FAIL because the component renders adjacent segment elements and changes source ownership.

- [ ] **Step 3: Implement a single chapter clock**

  Derive the chapter source from the first ready segment, render one audio element, update `activeParagraph` on `timeupdate` by locating the containing cue, store paragraph-local progress as `currentTime*1000 - start_ms`, seek clicks and resumes to cue start plus local position, and leave the media running when only the active cue changes. Preserve Range recovery, manual retry, final replay, voice/speed regeneration, and choice cancellation.

- [ ] **Step 4: Run component tests and verify GREEN**

  Run: `npx jest src/__tests__/components/StoryListeningExperience.test.tsx --runInBand`
  Expected: PASS.

### Task 4: Browser regression and release gates

**Files:**
- Modify: `frontend/e2e/story-listening-audio-transport.spec.ts`

**Interfaces:**
- Consumes: the chapter-cue API and single-element component.
- Produces: browser evidence that paragraph transitions do not create another media request or source switch.

- [ ] **Step 1: Add a failing browser regression**

  Serve one real playable chapter asset with multiple cue ranges. Assert every media request targets the one chapter URL, advance playback across the first cue, verify the UI moves to paragraph two while the same DOM audio node keeps playing, then click paragraph one and verify an in-place seek.

- [ ] **Step 2: Run focused desktop and mobile-profile E2E**

  Run from `frontend/`: `npx playwright test e2e/story-listening-audio-transport.spec.ts --project=core --workers=1`
  Run from `frontend/`: `npx playwright test e2e/story-listening-audio-transport.spec.ts --project='Mobile Safari' --no-deps --workers=1`
  Expected: PASS.

- [ ] **Step 3: Run all local gates**

  Run: `npm run test:types && npm run lint` from `frontend/`.
  Run: `./test.sh all` from the worktree root.
  Expected: every maintained layer passes.

- [ ] **Step 4: Commit, publish a Ready for review PR, and monitor it**

  Commit only the plan, tests, implementation, and required migration. Push `codex/fix-gapless-story-paragraphs-20260816`, create a non-draft PR, address review/CI findings with focused tests plus another full gate, and merge only after all required checks and review threads are clear.
