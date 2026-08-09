# Story Life Unified Narrative Loading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Every production change follows strict red-green-refactor.

**Goal:** Replace all long-form narrative loading surfaces with one calm, truthful and recoverable experience while preserving existing backend contracts and durable generation semantics.

**Architecture:** Add a presentation-only narrative loading module containing public types, a pure copy resolver, a one-shot delay hook and one component. Page adapters pass raw phases and transport states. Generation hooks own run-scoped cancellation, polling and activity-based recovery, while pages own full-screen versus inline transitions.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, Jest, Testing Library, Playwright.

## Global Constraints

- Work only in `/Users/luicy/story2/.worktrees/calm-narrative-loading-20260809` on `codex/calm-narrative-loading-20260809`, based on fetched `origin/main` commit `bca973c267e641ce5cde93ae9ec3cf51c6ea46aa`.
- This is one coherent frontend change. Do not modify backend APIs, database code, persistence schema, or generation task models.
- Do not change image, music, avatar, or button-level micro-loaders.
- Use loading-private colors exactly `#11100F`, `#0D0C0B`, `#F0ECE6`, `#8F8881`, `#34302C`, and `#71675D`; do not change the global theme.
- The only loading animation is a 2.8-second divider breath. Under `prefers-reduced-motion: reduce`, it is completely static.
- Never display “AI”, quality-tier names, estimated ranges, elapsed seconds, percentages, fake progress, spinners, pulses, skeletons, or shimmer on narrative loading surfaces.
- Active/delayed states have no action. Reconnecting/polling expose “重新连接”; failed exposes “重试”.
- Preserve one and only one `aria-live`/`role=status` region per loading instance.
- `AbortError` never starts polling. Polling and callbacks from a stale run never write current state. Real SSE activity resets the inactivity watchdog.
- Every task begins with a failing test whose failure is observed, then the minimal implementation, then refactoring while green.

---

### Task 1: Build the Unified Loading Contract and Visual Component

**Files:**
- Create: `frontend/src/components/narrative-loading/NarrativeLoadingState.tsx`
- Create: `frontend/src/components/narrative-loading/narrativeLoading.ts`
- Create: `frontend/src/hooks/useDelayedLoading.ts`
- Create: `frontend/src/__tests__/components/NarrativeLoadingState.test.tsx`
- Create: `frontend/src/__tests__/hooks/useDelayedLoading.test.ts`
- Modify: `frontend/src/app/globals.css`

**Produces:** exported types `NarrativeLoadingContext`, `NarrativeLoadingLayout`, `NarrativeLoadingOperation`, `NarrativeTransportState`; `resolveNarrativeLoadingCopy()`; `getNarrativeLoadingDelay()`; `useDelayedLoading()`; `NarrativeLoadingState`.

- [ ] Write table-driven failing copy tests for all six titles, real phase groups, operation-specific unknown fallback, delayed copy, transport actions, and no forbidden words/time ranges.
- [ ] Write failing component tests for screen/section/inline layouts, exactly one live region, no normal action, abnormal actions, and no spinner/skeleton/pulse semantics.
- [ ] Write failing fake-timer hook tests proving 250ms hydration, 15s character/ending, 30s auto, and 45/90/180s quality thresholds use one timeout and reset only when the loading identity changes.
- [ ] Observe RED, then implement the smallest pure module, hook, component and private CSS needed to pass.
- [ ] Add a reduced-motion test or stylesheet-capable assertion proving the divider is static under reduce; refactor and rerun the focused tests.

### Task 2: Integrate Hydration, Character Generation and Opening Streaming

**Files:**
- Modify: `frontend/src/app/create/page.tsx`
- Modify: `frontend/src/components/create/AutoGenScreen.tsx` or delete it after all imports are removed
- Modify: `frontend/src/app/story/opening/page.tsx`
- Modify: opening/create client helpers only as needed to expose already-available status callbacks
- Modify/Create: focused page/component tests for create and opening
- Delete after migration: `frontend/src/__tests__/components/AutoGenScreen.test.tsx`

**Consumes:** Task 1 loading API. **Produces:** actual auto-generation step labels and mutually exclusive opening screen/inline states.

- [ ] First add failing page tests for 250ms hydration visibility, single-step status, automatic generation’s actual current loop step, opening before first chunk, and opening after first chunk.
- [ ] Observe RED. Replace create-page `SkeletonStory` and generic auto-generation copy with the unified component; update the automatic loop at every real step transition.
- [ ] Make opening show a screen state only while story text is empty; after the first chunk render正文 plus one inline state until completion.
- [ ] Preserve existing success/error navigation behavior and retry semantics; do not invent a backend job or alter API payloads.
- [ ] Remove `AutoGenScreen` if no runtime import remains; rerun all focused create/opening tests.

### Task 3: Integrate Gameplay Rendering and Preserve the Mounted ChatBar

**Files:**
- Modify: `frontend/src/app/play/page.tsx`
- Modify: `frontend/src/components/game/ChatBar.tsx`
- Modify: `frontend/src/__tests__/components/ChatBar.test.tsx`
- Modify/Create: focused PlayPage tests
- Delete after migration: `frontend/src/components/game/SkeletonStory.tsx`
- Delete after migration: `frontend/src/components/game/GenerationBudgetProgress.tsx`
- Delete after migration: obsolete component tests

**Consumes:** Task 1 loading API and existing raw `processingMessage`. **Produces:** empty/partial story switching and visually hidden busy ChatBar without unmounting.

- [ ] Add failing tests for empty story section loading, partial story inline loading, delayed active state without time/action, reconnect/failed actions, and removal of the separate recovery card/page reload.
- [ ] Add failing ChatBar tests proving busy produces no visible DOM, closes open sheets, preserves local chat history through a busy/ready rerender, and fades back when ready.
- [ ] Observe RED. Replace both empty and partial gameplay loading branches with the unified component, using the real raw SSE phase and operation type.
- [ ] Keep `<ChatBar>` mounted in PlayPage; inside ChatBar close open surfaces on busy and return no visual UI until ready.
- [ ] Delete `SkeletonStory`, `GenerationBudgetProgress`, their dedicated shimmer CSS and obsolete tests after all imports are removed; rerun focused tests.

### Task 4: Harden Gameplay Run Isolation, Polling and Activity Watchdog

**Files:**
- Modify: `frontend/src/hooks/game/useEventGenerator.ts`
- Modify: `frontend/src/hooks/game/useChoiceHandler.ts` only where it shares transport reporting
- Modify: `frontend/src/hooks/game/usePhaseManager.ts`
- Modify: `frontend/src/hooks/game/usePlayGame.ts`
- Modify: `frontend/src/hooks/game/eventUtils.ts` as needed for run-safe callbacks
- Modify: `frontend/src/__tests__/hooks/useEventGenerator.test.ts`
- Modify: `frontend/src/__tests__/hooks/usePhaseManager.test.ts`
- Add focused tests for any extracted run/watchdog utility

**Produces:** transport state exposed to PlayPage and run-scoped recovery. Removes `STATUS_MESSAGES`, `getLoadingMessage`, and the public per-second elapsed interface.

- [ ] Add failing tests proving AbortError does not enter polling, a superseded run’s callbacks/polling cannot write, heartbeat/status/story activity resets inactivity timeout, and transitions are active → reconnecting → polling → failed/complete.
- [ ] Add a failing test proving phase management no longer schedules a one-second interval or exposes elapsed seconds/loading-message copy.
- [ ] Observe RED. Give each attempt a monotonically unique run token plus abort signal; guard every async write and polling iteration.
- [ ] Replace the fixed retry-status 60-second watchdog with a resettable inactivity timeout driven by actual SSE activity.
- [ ] Preserve durable event resume and complete validation. Do not change backend paths, payloads, Last-Event-ID behavior or persisted-event semantics.
- [ ] Rerun focused hook tests, including constants and SSE tests affected by callbacks.

### Task 5: Integrate Ending Error Recovery and Remove Remaining Legacy Loading APIs

**Files:**
- Modify: `frontend/src/app/ending/page.tsx`
- Create/Modify: focused ending page tests
- Modify: remaining `SkeletonStory` call sites found by repository search
- Delete or simplify: obsolete `STATUS_MESSAGES`, `getLoadingMessage`, elapsed-time tests and imports

- [ ] Add failing ending tests for initial loading, successful content, rejected request, empty response and retry success.
- [ ] Observe RED. Render the unified ending state and an explicit failed transport with a request retry action; never reload the page.
- [ ] Migrate every remaining `SkeletonStory`/`AutoGenScreen` runtime use. Confirm repository search has no production imports of deleted legacy components or generation-budget copy.
- [ ] Confirm story loading surfaces contain none of the forbidden terms or animation utilities; rerun focused page tests.

### Task 6: Replace the E2E Fixture and Complete Responsive Visual Acceptance

**Files:**
- Modify: `frontend/src/app/e2e-regression/page.tsx`
- Modify/Create: deterministic Playwright specs for narrative loading core/mobile
- Modify: existing `fast-generation-budget` expectations

- [ ] Add failing Playwright assertions for deterministic initial, partial正文, delayed, reconnecting, polling and failed fixture states, plus reduced motion.
- [ ] Observe RED. Replace the quality-budget fixture with controls/query modes that render the unified loading component without timers or network dependence.
- [ ] Verify core desktop at 1440×900 and mobile at 390×844: no horizontal overflow, no layout jump, no time copy, no full-screen loader after first chunk.
- [ ] Capture and inspect screenshots for initial, partial, delayed, reconnecting and failed states; correct spacing, type, contrast and mobile wrapping while retaining the approved tokens.
- [ ] Run focused Jest, `npm run test:types`, `npm run lint`, target Playwright core/mobile, then `./scripts/test-run-isolated.sh --namespace calm_narrative_loading all` from the repository root.
