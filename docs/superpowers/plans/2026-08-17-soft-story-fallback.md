# Soft Story Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the best renderable soft-warning story after the configured retry budget while preserving hard-error fail-closed behavior and explaining degraded delivery in the reading UI.

**Architecture:** The story generator will keep a ranked in-memory pool containing only candidates that have passed all hard gates. A selected fallback is returned as a normal `GameEvent` with a sanitized, persisted delivery notice; the SSE and save paths already serialize `GameEvent`, so the frontend only needs to preserve and render the new optional field. Existing structured terminal failures remain unchanged for all-hard or unusable attempts.

**Tech Stack:** Python 3.9, Pydantic v2, pytest, TypeScript, React 19, Zustand, Jest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-08-17-soft-story-fallback.md`

## Global Constraints

- Never place a candidate with a hard finding, empty output, broken structure, or unsafe content in the fallback pool.
- Respect configured prose-call budgets: fast 1, expert 3, master 10.
- Persist and expose only sanitized player-facing explanations, never internal diagnostics.
- Generate options and commit state only for the selected story.
- Preserve the existing old-story rollback behavior when replacement fails.

---

### Task 1: Backend candidate ranking and delivery metadata

**Files:**
- Modify: `src/ai/models.py`
- Modify: `src/ai/story_generator.py`
- Modify: `tests/test_story_generator_best_story_db.py`

**Interfaces:**
- Consumes: quick-validator warnings and Harness `ValidationResult.score` plus non-critical warning collections.
- Produces: `StoryDeliveryNotice` and optional `GameEvent.delivery_notice`; an internal deterministic soft-candidate ranking used only after hard gates pass.

- [ ] **Step 1: Write failing tests for a three-attempt expert soft fallback**

Add a test that returns three hard-valid stories with different soft-warning counts and asserts that all three prose calls occur, options are generated only for the best candidate, and the returned event contains a sanitized delivery notice with `attempts_used == 3`.

- [ ] **Step 2: Run the focused backend test and verify RED**

Run: `python3 -m pytest tests/test_story_generator_best_story_db.py -q`

Expected: FAIL because the first soft-warning candidate is currently returned immediately and `GameEvent` has no `delivery_notice`.

- [ ] **Step 3: Add the minimal event metadata and ranked candidate pool**

Add a Pydantic notice model with literal code `SOFT_VALIDATION_FALLBACK`, sanitized summary/reason, `retryable`, and `attempts_used`. Record a candidate only after every hard gate has passed. Compare literal rank tuples `(warning_count, -score, -length, request_index)` and continue within the existing budget when soft warnings remain.

- [ ] **Step 4: Add a hard-boundary regression test**

Add or extend a test proving a hard-rejected candidate is never returned as fallback and all-hard attempts still raise `StoryGenerationFailure` without calling option generation.

- [ ] **Step 5: Run backend tests and verify GREEN**

Run: `python3 -m pytest tests/test_story_generator_best_story_db.py tests/test_story_generation_failure_integrity.py tests/test_generation_failure_payload.py -q`

Expected: all selected tests pass.

### Task 2: Preserve the delivery notice through frontend event state

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/hooks/game/eventUtils.ts`
- Modify: `frontend/src/stores/useSessionStore.ts`
- Modify: `frontend/src/hooks/usePlayGame.ts`
- Modify: `frontend/src/hooks/game/useGameState.ts`
- Modify: `frontend/src/__tests__/hooks/eventUtils.test.ts`

**Interfaces:**
- Consumes: serialized `delivery_notice` on SSE completion and persisted `current_event` responses.
- Produces: `currentEvent.delivery_notice` across live completion, regeneration replacement, and page reload.

- [ ] **Step 1: Write failing live-completion and recovery tests**

Assert that `handleEventComplete` forwards a literal delivery notice to `setCurrentEvent`, and that persisted-event recovery retains the same notice.

- [ ] **Step 2: Run the focused Jest tests and verify RED**

Run: `npm run test:unit -- --runInBand src/__tests__/hooks/eventUtils.test.ts`

Expected: FAIL because event normalization currently drops `delivery_notice`.

- [ ] **Step 3: Extend shared event types and every normalization boundary**

Define `StoryDeliveryNotice`, add it to `GameEvent` and `CurrentEventData`, preserve it in `buildCurrentEvent`, session recovery, active-session recovery, and regeneration completion.

- [ ] **Step 4: Run focused state tests and verify GREEN**

Run: `npm run test:unit -- --runInBand src/__tests__/hooks/eventUtils.test.ts src/__tests__/hooks/usePlayGame.regenerate.test.ts`

Expected: all selected tests pass.

### Task 3: Render the soft fallback notice and verify boundaries

**Files:**
- Modify: `frontend/src/app/play/page.tsx`
- Modify: `frontend/src/__tests__/pages/PlayPage.test.tsx`

**Interfaces:**
- Consumes: `currentEvent.delivery_notice` and the existing coordinated regenerate handler.
- Produces: subdued reader-facing explanation plus a `重新生成` action; existing hard-failure alert remains unchanged.

- [ ] **Step 1: Write a failing page test**

Render an options-phase story with `SOFT_VALIDATION_FALLBACK` and assert the sanitized reason and a `重新生成` button are visible without the hard-failure alert copy.

- [ ] **Step 2: Run the focused page test and verify RED**

Run: `npm run test:unit -- --runInBand src/__tests__/pages/PlayPage.test.tsx`

Expected: FAIL because the page does not render delivery notices.

- [ ] **Step 3: Add the minimal subdued notice UI**

Render the notice only for the current non-history options view, use `text-xs` subdued styling, and wire the action to `handleCoordinatedRegenerate`.

- [ ] **Step 4: Run frontend tests and type checks**

Run: `npm run test:unit -- --runInBand src/__tests__/pages/PlayPage.test.tsx src/__tests__/hooks/eventUtils.test.ts src/__tests__/hooks/usePlayGame.regenerate.test.ts`

Run: `npm run test:types`

Expected: tests and TypeScript checks pass.

- [ ] **Step 5: Run the combined focused regression gate**

Run: `python3 -m pytest tests/test_story_generator_best_story_db.py tests/test_story_generation_failure_integrity.py tests/test_generation_failure_payload.py tests/test_daily_generation_transaction.py -q`

Run: `npm run test:unit -- --runInBand src/__tests__/pages/PlayPage.test.tsx src/__tests__/hooks/eventUtils.test.ts src/__tests__/hooks/usePlayGame.regenerate.test.ts`

Expected: both backend and frontend focused gates pass with no failures.
