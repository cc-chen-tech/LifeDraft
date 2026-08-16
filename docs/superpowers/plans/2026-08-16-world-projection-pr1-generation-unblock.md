# PR 1: Daily Generation Unblock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unblock daily generation by routing missing events correctly, coalescing duplicate work, preserving accepted stories during replacement, exposing durable retry feedback, and preventing stale world constraints from consuming candidate budget.

**Architecture:** Add one backend intent resolver in front of both daily SSE paths and reuse the existing session coordinator with a normalized per-day key. Add a provisional world-freshness view that removes stale spatial/commitment/causal data from hard validation while retaining accepted story history as canonical prompt context. Frontend retry and regenerate actions share one synchronous in-flight guard and one visible state surface.

**Tech Stack:** Python 3, FastAPI SSE, Pydantic, pytest, TypeScript, React hooks, Jest/Testing Library.

**Spec:** `docs/superpowers/specs/2026-08-16-versioned-async-world-projection-design.md`

## Global Constraints

- Scope is calendar timeline v2 only; opening stories and the legacy weekly timeline keep their existing behavior.
- `/event` remains the public ensure-current endpoint and `/regenerate-stream` remains the public replacement endpoint.
- A failed replacement must preserve the accepted story, options, revision, relationship state, and scene media.
- Soft quality findings and internal diagnostics are not shown in the reading flow.
- A player-triggered retry after terminal failure receives a new operation ID and a fresh quality-tier budget.
- PR 1 must deploy and roll back without the projection table introduced by PR 2.

---

### Task 1: Centralize complete-event and generation-intent resolution

**Files:**
- Create: `src/game/daily_generation_intent.py`
- Test: `tests/test_daily_generation_intent.py`

**Interfaces:**
- Consumes: `src.ai.models.GameEvent` and dict-shaped `current_event_data`.
- Produces: `RequestedDailyIntent`, `ResolvedDailyMode`, `DailyGenerationResolution`, `is_complete_daily_event(value)`, and `resolve_daily_generation_intent(requested, current_event)`.

- [ ] **Step 1: Write failing resolver tests**

```python
def test_replace_without_complete_event_resolves_to_generate_missing() -> None:
    resolution = resolve_daily_generation_intent("replace_current", None)
    assert resolution.resolved_mode == "generate_missing"
    assert resolution.base_event_id == ""
    assert resolution.base_revision == 0


def test_replace_with_complete_event_binds_base_revision() -> None:
    event = GameEvent(
        event_id="day-5",
        revision=3,
        event_description="孙悟空抵达东海。",
        options=[
            EventOption(text="拜访龙王", effects={}),
            EventOption(text="先观察海岸", effects={}),
        ],
    )
    resolution = resolve_daily_generation_intent("replace_current", event)
    assert resolution.resolved_mode == "replace_current"
    assert (resolution.base_event_id, resolution.base_revision) == ("day-5", 3)


@pytest.mark.parametrize("value", [None, {}, {"event_id": "x", "revision": 1}])
def test_incomplete_event_is_not_replaceable(value) -> None:
    assert is_complete_daily_event(value) is False
```

- [ ] **Step 2: Run the tests and verify the missing module failure**

Run: `python -m pytest tests/test_daily_generation_intent.py -q`

Expected: collection fails because `src.game.daily_generation_intent` does not exist.

- [ ] **Step 3: Implement the resolver as a pure module**

```python
RequestedDailyIntent = Literal["ensure_current", "replace_current"]
ResolvedDailyMode = Literal["return_existing", "generate_missing", "replace_current"]


@dataclass(frozen=True)
class DailyGenerationResolution:
    requested_intent: RequestedDailyIntent
    resolved_mode: ResolvedDailyMode
    base_event_id: str
    base_revision: int


def is_complete_daily_event(value: object) -> bool:
    try:
        event = value if isinstance(value, GameEvent) else GameEvent.model_validate(value)
    except (TypeError, ValueError, ValidationError):
        return False
    return bool(
        event.event_id
        and event.revision >= 1
        and event.event_description.strip()
        and len(event.options) >= 2
    )


def resolve_daily_generation_intent(
    requested: RequestedDailyIntent,
    current_event: object,
) -> DailyGenerationResolution:
    complete = is_complete_daily_event(current_event)
    if requested == "ensure_current":
        mode: ResolvedDailyMode = "return_existing" if complete else "generate_missing"
    else:
        mode = "replace_current" if complete else "generate_missing"
    event = current_event if isinstance(current_event, GameEvent) and complete else None
    return DailyGenerationResolution(
        requested_intent=requested,
        resolved_mode=mode,
        base_event_id=str(event.event_id) if event else "",
        base_revision=int(event.revision) if event else 0,
    )
```

- [ ] **Step 4: Run the resolver tests**

Run: `python -m pytest tests/test_daily_generation_intent.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the resolver**

```bash
git add src/game/daily_generation_intent.py tests/test_daily_generation_intent.py
git commit -m "fix: resolve daily generation intent from saved event"
```

### Task 2: Coalesce missing generation and replacement in the backend

**Files:**
- Modify: `src/api/services/event_generation_operation.py`
- Modify: `src/api/routers/gameplay/sse_helpers.py`
- Modify: `src/api/routers/story.py`
- Test: `tests/test_event_generation_contract.py`
- Test: `tests/test_round_event_sse_terminal_contracts.py`
- Test: `tests/test_api_story.py`

**Interfaces:**
- Consumes: `DailyGenerationResolution` from Task 1.
- Produces: `EventGenerationKey.resolved_mode/base_event_id/base_revision`, `EventGenerationCoordinator.get_or_create_for_slot(key)`, and a single `_get_or_start_daily_operation(...)` used by both daily SSE paths.

- [ ] **Step 1: Add failing coordinator and fallback tests**

```python
def test_daily_same_slot_requests_join_running_operation() -> None:
    coordinator = EventGenerationCoordinator()
    first_key = EventGenerationKey(
        game_id=156, week=31, round_number=5,
        stage="daily", resolved_mode="generate_missing",
        base_event_id="", base_revision=0,
    )
    second_key = replace(first_key, stage="daily-reconnect")
    first, first_start = coordinator.get_or_create_for_slot(first_key)
    second, second_start = coordinator.get_or_create_for_slot(second_key)
    assert first is second
    assert (first_start, second_start) == (True, False)


@pytest.mark.asyncio
async def test_daily_regenerate_without_current_event_runs_missing_generator(monkeypatch) -> None:
    loop = daily_loop(current_event=None)
    operation, should_start = sse_helpers._get_or_start_daily_operation(
        loop, 156, session_with_coordinator(), "replace_current", None
    )
    assert should_start is True
    assert operation.key.resolved_mode == "generate_missing"
```

At the API layer, assert `GET /api/games/{id}/regenerate-stream` returns an SSE complete frame for a daily save without `current_event_data`, rather than an error frame.

- [ ] **Step 2: Run focused backend tests and verify failures**

Run: `python -m pytest tests/test_event_generation_contract.py tests/test_round_event_sse_terminal_contracts.py tests/test_api_story.py -q`

Expected: failures mention missing key fields, `get_or_create_for_slot`, and `_get_or_start_daily_operation`.

- [ ] **Step 3: Extend the coordinator without breaking legacy callers**

Add defaulted fields to `EventGenerationKey`:

```python
resolved_mode: str = "event"
base_event_id: str = ""
base_revision: int = 0
```

Add an atomic join method:

```python
def get_or_create_for_slot(self, key: EventGenerationKey):
    with self._lock:
        current = self._current
        if current is not None and current.status == "running":
            same_slot = (
                current.key.game_id,
                current.key.week,
                current.key.round_number,
            ) == (key.game_id, key.week, key.round_number)
            if same_slot:
                return current, False
            raise EventGenerationConflict(f"generation already running for {current.key}")
        return self._create_unlocked(key)
```

Refactor existing creation logic into `_create_unlocked` so the method never reacquires a non-reentrant lock.

- [ ] **Step 4: Replace daily regeneration startup with one intent-aware worker**

In `sse_helpers.py`, implement `_get_or_start_daily_operation(game_loop, game_id, session, requested_intent, last_event_id)`. Resolve under `_get_game_state_lock(game_id)`, return an existing complete event for `return_existing`, and select one worker body:

```python
if resolution.resolved_mode == "replace_current":
    event = regenerate_daily_event_atomically(...)
else:
    event = game_loop.generate_round_event(
        operation_id=operation.operation_id,
        stream_callback=operation.publish_story,
        status_callback=operation.publish_phase,
        session=session,
    )
```

Publish an initial status payload containing `operation_id`, `requested_intent`, and `resolved_mode`. The router continues returning HTTP 200 SSE; application failures remain terminal SSE error frames.

- [ ] **Step 5: Run backend focused tests**

Run: `python -m pytest tests/test_event_generation_contract.py tests/test_round_event_sse_terminal_contracts.py tests/test_api_story.py tests/test_daily_event_revision.py -q`

Expected: all pass, including no-current defensive fallback and existing atomic replacement tests.

- [ ] **Step 6: Commit the backend single-flight slice**

```bash
git add src/api/services/event_generation_operation.py src/api/routers/gameplay/sse_helpers.py src/api/routers/story.py tests/test_event_generation_contract.py tests/test_round_event_sse_terminal_contracts.py tests/test_api_story.py
git commit -m "fix: coalesce daily generation and replacement"
```

### Task 3: Downgrade stale world constraints before candidate validation

**Files:**
- Create: `src/game/world_constraint_freshness.py`
- Create: `src/game/world_projection_coverage.py`
- Modify: `src/game/world_model.py`
- Modify: `src/game/round/event_generator.py`
- Modify: `src/ai/story_generator.py`
- Test: `tests/test_world_constraint_freshness.py`
- Test: `tests/test_world_projection_coverage.py`
- Test: `tests/test_story_generation_budget_tracking.py`

**Interfaces:**
- Produces: `WorldConstraintFreshness`, `detect_world_change_signals(story, options, tracked_state)`, `derive_legacy_freshness(day_history)`, and `build_validation_world_model(player_state)`.
- Contract: stale location, commitment, and causal entries are absent from the hard-validation model but remain in `soft_context`; accepted day-history prose and choices remain canonical prompt context.

- [ ] **Step 1: Write failing freshness and budget tests**

```python
def test_suspicious_empty_world_updates_make_legacy_constraints_stale() -> None:
    history = [{
        "day_index": 4,
        "event_description": "黑袍人抵达东海，完成了与孙悟空的约定。",
        "postprocessing_status": "complete",
        "postprocessing": {"world": empty_world_patch()},
    }]
    freshness = derive_legacy_freshness(history)
    assert freshness.stale_from_day_index == 4
    assert freshness.reason == "suspicious_empty_world_projection"


def test_stale_spatial_commitment_and_causal_findings_do_not_spend_budget() -> None:
    result = generate_with_stale_world_fixture(max_attempts=3)
    assert result.accepted is True
    assert result.provider_requests_used == 1
    assert result.hard_findings == []
```

- [ ] **Step 2: Run the tests and verify failures**

Run: `python -m pytest tests/test_world_constraint_freshness.py tests/test_story_generation_budget_tracking.py -q`

Expected: freshness module is missing and stale findings still enter retry logic.

- [ ] **Step 3: Implement the provisional freshness view**

```python
@dataclass(frozen=True)
class WorldConstraintFreshness:
    stale_from_day_index: int | None
    reason: str | None

    @property
    def world_derivations_are_fresh(self) -> bool:
        return self.stale_from_day_index is None
```

Implement `detect_world_change_signals` as an evidence-only result containing `requires_nonempty_patch`, `categories`, and matched spans. In PR 1 it covers tracked-character movement, commitment lifecycle, and known causal cause/result terms; it never constructs a patch. Scan day history oldest-first and mark stale at the first pending/failed record, or at the first complete record whose seven world lists are empty while this detector reports required changes. PR 2 extends the same module and interface with typed projection validation.

`build_validation_world_model` builds the ordinary `WorldModel`, then clears `character_locations`, `active_commitments`, and `causal_chains` when freshness is stale. It returns the removed records rendered as `soft_context` plus the canonical day-history tail.

- [ ] **Step 4: Wire the hard model and soft context into generation**

In `RoundEventGenerator`/`StoryGenerator`, pass only the filtered model to harness validators. Add accepted story and choice text after the applied watermark to prompt context. Log each downgrade as `stale_world_constraint_downgraded` with game/day/category; do not create warning text for the player.

- [ ] **Step 5: Verify candidate budget behavior**

Run: `python -m pytest tests/test_world_constraint_freshness.py tests/test_world_projection_coverage.py tests/test_story_generation_budget_tracking.py tests/test_world_model_constraint_matrix_contracts.py tests/test_story_validation_findings.py -q`

Expected: stale-only contradictions do not retry; deterministic structure and accepted-story contradictions still reject.

- [ ] **Step 6: Commit the freshness boundary**

```bash
git add src/game/world_constraint_freshness.py src/game/world_projection_coverage.py src/game/world_model.py src/game/round/event_generator.py src/ai/story_generator.py tests/test_world_constraint_freshness.py tests/test_world_projection_coverage.py tests/test_story_generation_budget_tracking.py
git commit -m "fix: soften stale world constraints during generation"
```

### Task 4: Unify frontend retry/regenerate commands and preserve accepted prose

**Files:**
- Create: `frontend/src/hooks/game/dailyGenerationCommand.ts`
- Modify: `frontend/src/hooks/game/useGameState.ts`
- Modify: `frontend/src/hooks/game/useEventGenerator.ts`
- Modify: `frontend/src/hooks/usePlayGame.ts`
- Modify: `frontend/src/lib/sse.ts`
- Test: `frontend/src/__tests__/hooks/useGameState.test.ts`
- Test: `frontend/src/__tests__/hooks/useEventGenerator.test.ts`
- Test: `frontend/src/__tests__/hooks/usePlayGame.regenerate.test.ts`
- Test: `frontend/src/__tests__/lib/sse.test.ts`

**Interfaces:**
- Produces: `DailyGenerationCommandState`, `isCompleteClientEvent(event)`, and the single `handleDailyStoryAction()` returned by `useGameState`. `usePlayGame` owns the state/ref and passes them to both `useEventGenerator` and `useGameState`.
- `DailyGenerationCommandState.status` is `idle | starting | running | succeeded | failed`; it carries resolved mode, operation ID, attempt progress, and terminal failure.

- [ ] **Step 1: Write failing routing, double-click, and preservation tests**

```typescript
it("uses event generation when no complete current event exists", async () => {
  mockGameStore.currentEvent = null;
  await act(async () => result.current.handleDailyStoryAction());
  expect(generateEventRef.current).toHaveBeenCalledTimes(1);
  expect(streamRegenerate).not.toHaveBeenCalled();
});

it("coalesces two synchronous clicks", async () => {
  act(() => {
    void result.current.handleDailyStoryAction();
    void result.current.handleDailyStoryAction();
  });
  expect(streamRegenerate).toHaveBeenCalledTimes(1);
});

it("keeps accepted story visible until replacement completes", async () => {
  await startReplacement();
  expect(mockSetStoryText).not.toHaveBeenCalledWith("");
  expect(mockSetCurrentEvent).not.toHaveBeenCalledWith(null);
});
```

- [ ] **Step 2: Run focused Jest tests and verify failures**

Run: `cd frontend && npx jest src/__tests__/hooks/useGameState.test.ts src/__tests__/hooks/useEventGenerator.test.ts src/__tests__/hooks/usePlayGame.regenerate.test.ts src/__tests__/lib/sse.test.ts --runInBand`

Expected: missing unified handler/state and current implementation clears story before streaming.

- [ ] **Step 3: Implement the pure client resolver and command state**

```typescript
export type DailyGenerationCommandStatus = "idle" | "starting" | "running" | "succeeded" | "failed";
export interface DailyGenerationCommandState {
  status: DailyGenerationCommandStatus;
  mode: "generate_missing" | "replace_current" | null;
  operationId: string | null;
  attempt: number | null;
  maxAttempts: number | null;
  failure: GenerationFailurePayload | null;
}
```

`isCompleteClientEvent` requires non-empty story, at least two options, event ID, and revision >= 1. In `useGameState`, set the ref guard and `starting` state before reading storage or awaiting anything. Route missing events to `generateEventRef.current()` and complete events to the replacement stream.

Move the command state and synchronous in-flight ref to `usePlayGame`. `useEventGenerator` updates the same state for automatic next-day `/event` calls: starting before fetch, running on the first status/story activity, succeeded on persisted completion, and failed on terminal error. Calling missing-event retry through `useGameState` joins that same in-flight promise instead of creating a second state machine.

- [ ] **Step 4: Buffer replacement prose off-screen**

Use `replacementBufferRef` for `onStory` chunks. Clear only that buffer on backend retry. On complete, validate the server story/options, then atomically call `setStoryText`, `setOptions`, and `setCurrentEvent`. On error leave the old store untouched and set the command failure.

Extend `StreamStatusPayload` with optional `operation_id`, `requested_intent`, and `resolved_mode`; copy them into command state.

- [ ] **Step 5: Run focused frontend tests**

Run: `cd frontend && npx jest src/__tests__/hooks/useGameState.test.ts src/__tests__/hooks/useEventGenerator.test.ts src/__tests__/hooks/usePlayGame.regenerate.test.ts src/__tests__/lib/sse.test.ts --runInBand`

Expected: all pass.

- [ ] **Step 6: Commit the unified frontend command**

```bash
git add frontend/src/hooks/game/dailyGenerationCommand.ts frontend/src/hooks/game/useGameState.ts frontend/src/hooks/game/useEventGenerator.ts frontend/src/hooks/usePlayGame.ts frontend/src/lib/sse.ts frontend/src/__tests__/hooks/useGameState.test.ts frontend/src/__tests__/hooks/useEventGenerator.test.ts frontend/src/__tests__/hooks/usePlayGame.regenerate.test.ts frontend/src/__tests__/lib/sse.test.ts
git commit -m "fix: unify daily story retry commands"
```

### Task 5: Render durable status inside the daily transition surface

**Files:**
- Modify: `frontend/src/components/game/DailyTransitionLayer.tsx`
- Modify: `frontend/src/hooks/game/useDailyTransition.ts`
- Modify: `frontend/src/app/play/page.tsx`
- Test: `frontend/src/__tests__/components/DailyTransitionLayer.test.tsx`
- Test: `frontend/src/__tests__/hooks/useDailyTransition.test.tsx`
- Test: `frontend/src/__tests__/pages/PlayPage.test.tsx`

**Interfaces:**
- Consumes: `DailyGenerationCommandState` from Task 4.
- Produces: a transition layer that owns idle/running/failed feedback without relying on page toast visibility.

- [ ] **Step 1: Write failing transition UI tests**

```tsx
it("locks retry immediately while generation is running", () => {
  render(<DailyTransitionLayer {...baseProps} generation={runningState} />);
  expect(screen.getByRole("button", { name: "正在生成" })).toBeDisabled();
  expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
});

it("keeps terminal failure visible on the transition layer", () => {
  render(<DailyTransitionLayer {...baseProps} generation={failedState("故事生成未能完成")} />);
  expect(screen.getByRole("alert")).toHaveTextContent("故事生成未能完成");
  expect(screen.getByRole("button", { name: "再次生成" })).toBeEnabled();
});
```

- [ ] **Step 2: Run focused UI tests and verify failures**

Run: `cd frontend && npx jest src/__tests__/components/DailyTransitionLayer.test.tsx src/__tests__/hooks/useDailyTransition.test.tsx src/__tests__/pages/PlayPage.test.tsx --runInBand`

Expected: component lacks generation state and failure alert props.

- [ ] **Step 3: Implement the transition state rendering**

Replace the `failed: boolean` prop with `generation: DailyGenerationCommandState`. Render:

- idle/failed resume: “下一日故事暂未生成” and enabled retry;
- starting/running: disabled “正在生成”, spinner, and `第 n/m 次` when available;
- terminal failed: `role="alert"`, the safe summary, and “再次生成”;
- success: let the existing phase/story effect dismiss the layer.

In `PlayPage`, pass the same `handleDailyStoryAction` to the transition layer, generation failure card, ChatBar, and PlayTools. Remove `dailyTransition.active` from the conditions that suppress terminal generation feedback; world-projection diagnostics remain hidden.

- [ ] **Step 4: Run UI tests and typecheck**

Run: `cd frontend && npx jest src/__tests__/components/DailyTransitionLayer.test.tsx src/__tests__/hooks/useDailyTransition.test.tsx src/__tests__/pages/PlayPage.test.tsx --runInBand && npx tsc --noEmit`

Expected: tests and TypeScript compilation pass.

- [ ] **Step 5: Commit the durable transition feedback**

```bash
git add frontend/src/components/game/DailyTransitionLayer.tsx frontend/src/hooks/game/useDailyTransition.ts frontend/src/app/play/page.tsx frontend/src/__tests__/components/DailyTransitionLayer.test.tsx frontend/src/__tests__/hooks/useDailyTransition.test.tsx frontend/src/__tests__/pages/PlayPage.test.tsx
git commit -m "fix: show durable daily generation feedback"
```

### Task 6: Verify PR 1 as an independently deployable release

**Files:**
- Modify only if a test exposes a defect in PR 1 scope.

**Interfaces:**
- Produces: local release evidence for PR 1; no projection table or repair mutation.

- [ ] **Step 1: Run the focused backend regression set**

Run: `python -m pytest tests/test_daily_generation_intent.py tests/test_event_generation_contract.py tests/test_round_event_sse_terminal_contracts.py tests/test_api_story.py tests/test_daily_event_revision.py tests/test_story_generation_budget_tracking.py tests/test_world_constraint_freshness.py -q`

Expected: exit 0.

- [ ] **Step 2: Run the focused frontend regression set**

Run: `cd frontend && npx jest src/__tests__/hooks/useGameState.test.ts src/__tests__/hooks/useEventGenerator.test.ts src/__tests__/hooks/usePlayGame.regenerate.test.ts src/__tests__/components/DailyTransitionLayer.test.tsx src/__tests__/hooks/useDailyTransition.test.tsx src/__tests__/pages/PlayPage.test.tsx src/__tests__/lib/sse.test.ts --runInBand`

Expected: exit 0.

- [ ] **Step 3: Run repository gates**

Run: `./test.sh preflight && ./test.sh contract && ./test.sh db && ./test.sh frontend`

Expected: every command exits 0. Run `./test.sh all` only in the designated integration worktree after no other E2E owner holds the lock.

- [ ] **Step 4: Confirm the deploy/rollback boundary**

Run: `git diff origin/main...HEAD -- src frontend tests`

Expected: no `DailyWorldProjection` table, no projection worker, and no production repair script. Reverting PR 1 restores prior behavior without a schema rollback.

- [ ] **Step 5: Record the verification commit if gate-only fixes were needed**

```bash
git add src frontend tests
git commit -m "test: close daily generation unblock regressions"
```

Skip this commit only when `git status --short` is empty.
