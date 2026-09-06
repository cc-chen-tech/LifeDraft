# Streaming Story TTS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make MiniMax story narration start when the first validated scene is ready, continue in an ordered scene queue, and retain a complete chapter cache when all scenes finish.

**Architecture:** Keep the existing durable chapter job and add scene-level readiness to its segments. MiniMax receives one scene at a time with direct native voice/emotion parameters; the backend stores each validated MP3 and exposes it immediately, while a later assembly step preserves the existing full-chapter asset path. The frontend consumes ready segment URLs as a queue and keeps the old chapter URL path for completed/cache hits.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, MiniMax HTTP/WebSocket TTS, React/TypeScript, pytest, Vitest.

**Spec:** `docs/superpowers/plans/2026-09-06-streaming-story-tts.md`

## Global Constraints

- MiniMax native emotion values only: `happy`, `sad`, `angry`, `fearful`, `disgusted`, `surprised`, `calm`, `whipser`.
- Invalid narration plans must return their concrete validation errors to the story model retry path; no silent emotion downgrade.
- Existing chapter cache, resume progress, deterministic test provider, and current-story validation remain compatible.
- Work only in `/Users/luicy/story2/.worktrees/streaming-story-tts` on `codex/streaming-story-tts-20260906`.

### Task 1: MiniMax native narration contract

**Files:**
- Modify: `src/services/minimax_story_tts_provider.py`
- Test: `tests/test_minimax_tts_protocol_parser_contracts.py`

- [x] Add failing tests for the eight exact emotions, direct `emotion` payload inclusion, inline vocal cues, and the official WebSocket `connected_success -> task_start -> task_continue -> task_finish` message sequence.
- [x] Run the focused tests and confirm failure against the current payload/protocol implementation.
- [x] Implement constants, strict validation, payload construction, and protocol framing without changing the existing async client contract.
- [x] Run the focused tests and the existing MiniMax contract suite.

### Task 2: Scene-ready backend job state

**Files:**
- Modify: `src/services/story_voice_repository.py`, `src/services/story_voice_reading.py`, `src/api/schemas.py`
- Test: `tests/test_story_voice_streaming_contract.py`

- [x] Add failing tests proving that a completed first segment returns `status=processing`, its `audio_url`, and an ordered segment response before later segments finish.
- [x] Implement per-segment generation and durable segment asset metadata; keep terminal `ready` reserved for complete chapter assembly.
- [x] Add an explicit segment failure response carrying the provider error, rather than downgrading to another emotion or voice.
- [x] Run focused service tests plus all existing story voice DB/route tests.

### Task 3: Voice catalog and preview contract

**Files:**
- Create: `src/services/minimax_voice_catalog.py`
- Modify: `src/api/schemas.py`, `src/api/routers/voice_reading.py`, `src/services/story_voice_reading.py`, `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`
- Test: `tests/test_minimax_voice_catalog_contract.py`

- [x] Add failing tests for recommended voices, language groups, search results, and preview request validation.
- [x] Implement the catalog response with official MiniMax IDs, labels, language/group metadata, and an on-demand preview endpoint using the same cache-safe provider path.
- [x] Preserve the legacy aliases in request validation so existing saved settings still resolve.
- [x] Run backend catalog/route tests and TypeScript typecheck.

### Task 4: Queue playback UI

**Files:**
- Modify: `frontend/src/components/game/StoryListeningExperience.tsx`, `frontend/src/lib/types.ts`
- Test: `frontend/src/__tests__/components/StoryListeningExperience.test.tsx`

- [x] Add failing tests for starting playback from segment 0 while the job remains processing, automatic transition to the next ready segment, and waiting briefly when the next segment is not ready.
- [x] Replace the single chapter source selection with a stable ordered segment queue while retaining resume/progress and completed chapter URL behavior.
- [x] Add recommended voice selection plus searchable “全部音色库” and preview controls using the catalog API.
- [x] Run the focused Vitest suite and frontend typecheck/build.

### Task 5: Regression and delivery verification

- [x] Run focused backend tests, all story voice tests, and relevant frontend tests.
- [x] Run lint/typecheck/build commands available in the repository.
- [x] Inspect `git diff`, verify only the isolated branch changed, and record deployment as not performed unless explicitly requested.
