# P1-1 Durable Event Generation Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure one event-generation job exists per `(game_id, week, round, stage)`, and make refresh/recovery attach to that job instead of cancelling or restarting it.

**Architecture:** Introduce a thread-safe per-session event operation whose lifetime is independent of any SSE response. The background worker writes phases, story chunks, result, and error into the operation; every SSE connection is only a subscriber that replays from `Last-Event-ID` and waits for the same result. The frontend records SSE event IDs together with the already-rendered story snapshot and reconnects in resume mode without clearing state or using `force`; an orphaned cursor without its matching story snapshot falls back to replay from the beginning.

**Tech Stack:** Python 3.11, FastAPI, asyncio, `ThreadPoolExecutor`, threading locks, React 19, TypeScript, Jest, Testing Library.

## Global Constraints

- P1-1 is the only product issue in this branch and PR.
- The stable operation key is exactly `(game_id, week, round_number, "event")`.
- A browser disconnect must not cancel, reset, or duplicate the background generation job.
- No fixed 60-second timer may clear server-side generation ownership.
- A recovery action reconnects to the current operation; only an explicitly failed operation may start a new attempt.
- Existing game result, story text, and options remain visible during recovery.
- Every production-code change follows red-green-refactor and is committed in a self-contained unit.
- The production deployment currently runs one Uvicorn process; cross-process coordination is outside this PR, but the operation API must not preclude a persistent coordinator later.

---

## Root-Cause Record

The current failure is a lifecycle race, not only a slow model call:

1. `frontend/src/hooks/game/useEventGenerator.ts:326-342` aborts the active SSE, clears local ownership flags, empties options, changes phase to `loading`, and invokes `generateEvent({ force: true })`.
2. `src/api/routers/gameplay/events.py` owns an `asyncio.Lock` only for the lifetime of the `StreamingResponse` generator. Client cancellation closes that generator and releases the lock while the submitted worker thread can still be generating.
3. The route checks `game_loop._generating`, but `RoundSystemMixin.generate_round_event()` delegates to `RoundEventGenerator`, which updates its own `RoundEventGenerator._generating`. The route-visible field is therefore stale.
4. Both the route and generator treat elapsed wall time as proof that ownership is stale and clear it at 60/120 seconds. Production generation commonly lasts 80-120 seconds, so this explicitly permits overlap.
5. Existing tests encode the faulty behavior: one Jest test expects recovery to force a new request, while Python contract tests expect a 60-second forced reset.

The single hypothesis to test is: decoupling one operation from SSE subscriber lifetimes and reconnecting by event ID eliminates duplicate generation without changing the model-generation pipeline.

## File Map

- Create `src/api/services/event_generation_operation.py`: thread-safe operation key, state, chunk replay, and coordinator.
- Modify `src/api/session_store.py`: attach one coordinator to every `GameLoopSession`; keep the generic SSE cache for non-event streams unchanged.
- Modify `src/api/routers/gameplay/sse_helpers.py`: start a worker once, publish into the operation, and stream operation snapshots to any number of subscribers.
- Modify `src/api/routers/gameplay/events.py`: remove response-lifetime locking and stale timeout resets; make streaming and sync endpoints share the operation.
- Modify `src/game/round/event_generator.py`: reject concurrent direct calls without wall-clock ownership reset.
- Modify `frontend/src/lib/sse.ts`: parse `id:` lines, report event IDs, and send `Last-Event-ID` when resuming.
- Modify `frontend/src/hooks/game/useEventGenerator.ts`: distinguish resume from retry and remove `force` behavior.
- Modify `tests/test_event_generation_contract.py`, `tests/test_event_generation_race_db.py`, `tests/test_events_router.py`, and `tests/test_api_gameplay.py`: replace lock/timeout contracts with operation-ownership contracts.
- Modify `frontend/src/__tests__/lib/sse.test.ts` and `frontend/src/__tests__/hooks/useEventGenerator.test.ts`: prove ID propagation and read-only recovery.

---

### Task 1: Add the Thread-Safe Event Operation

**Files:**
- Create: `src/api/services/event_generation_operation.py`
- Modify: `src/api/session_store.py`
- Test: `tests/test_event_generation_contract.py`

**Interfaces:**
- Produces: `EventGenerationKey(game_id, week, round_number, stage)`.
- Produces: `EventGenerationOperation.publish_story()`, `publish_phase()`, `complete()`, `fail()`, and `snapshot_after()`.
- Produces: `EventGenerationCoordinator.get_or_create()` returning `(operation, should_start)`.
- Raises: `EventGenerationConflict` if a different operation key is still running.
- Consumed by: Task 2 backend worker and both gameplay endpoints.

- [x] **Step 1: Replace the obsolete lock/timeout contract tests with failing operation tests**

Add these cases to `tests/test_event_generation_contract.py` and remove imports/assertions for `_get_game_lock`, `game_loop._generating_start_time`, and forced timeout reset:

```python
from concurrent.futures import ThreadPoolExecutor

from src.api.services.event_generation_operation import (
    EventGenerationConflict,
    EventGenerationCoordinator,
    EventGenerationKey,
)


def test_same_operation_key_has_exactly_one_starter():
    coordinator = EventGenerationCoordinator()
    key = EventGenerationKey(7, 3, 1, "event")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: coordinator.get_or_create(key), range(8)))

    assert sum(1 for _, should_start in results if should_start) == 1
    assert len({id(operation) for operation, _ in results}) == 1


def test_different_key_cannot_replace_running_operation():
    coordinator = EventGenerationCoordinator()
    coordinator.get_or_create(EventGenerationKey(7, 3, 1, "event"))

    with pytest.raises(EventGenerationConflict):
        coordinator.get_or_create(EventGenerationKey(7, 3, 2, "event"))


def test_failed_operation_can_start_a_new_attempt_for_same_key():
    coordinator = EventGenerationCoordinator()
    key = EventGenerationKey(7, 3, 1, "event")
    first, first_should_start = coordinator.get_or_create(key)
    first.fail("provider unavailable")

    second, second_should_start = coordinator.get_or_create(key)

    assert first_should_start is True
    assert second_should_start is True
    assert second is not first


def test_snapshot_replays_only_chunks_after_last_event_id():
    coordinator = EventGenerationCoordinator()
    operation, _ = coordinator.get_or_create(EventGenerationKey(7, 3, 1, "event"))
    assert operation.publish_story("A") == 0
    assert operation.publish_story("B") == 1

    snapshot = operation.snapshot_after(0)

    assert snapshot.chunks == ((1, "B"),)
```

- [x] **Step 2: Run the new contract tests and verify RED**

Run:

```bash
python -m pytest tests/test_event_generation_contract.py -q
```

Expected: collection fails because `src.api.services.event_generation_operation` does not exist.

- [x] **Step 3: Implement the operation and coordinator**

Create `src/api/services/event_generation_operation.py` with these public types and semantics:

```python
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Literal, Optional

EventGenerationStatus = Literal["running", "completed", "failed"]


@dataclass(frozen=True)
class EventGenerationKey:
    game_id: int
    week: int
    round_number: int
    stage: str = "event"


@dataclass(frozen=True)
class EventGenerationSnapshot:
    status: EventGenerationStatus
    phase: str
    chunks: tuple[tuple[int, str], ...]
    result: Optional[Any]
    error: Optional[str]


class EventGenerationConflict(RuntimeError):
    pass


class EventGenerationOperation:
    MAX_CHUNKS = 500

    def __init__(self, key: EventGenerationKey):
        self.key = key
        self._lock = threading.RLock()
        self._status: EventGenerationStatus = "running"
        self._phase = "preparing"
        self._chunks: list[tuple[int, str]] = []
        self._next_event_id = 0
        self._result: Optional[Any] = None
        self._error: Optional[str] = None

    @property
    def status(self) -> EventGenerationStatus:
        with self._lock:
            return self._status

    def publish_story(self, chunk: str) -> int:
        with self._lock:
            event_id = self._next_event_id
            self._next_event_id += 1
            self._chunks.append((event_id, chunk))
            if len(self._chunks) > self.MAX_CHUNKS:
                self._chunks = self._chunks[-self.MAX_CHUNKS :]
            return event_id

    def publish_phase(self, phase: str) -> None:
        with self._lock:
            self._phase = phase

    def complete(self, result: Any) -> None:
        with self._lock:
            self._result = result
            self._error = None
            self._status = "completed"
            self._phase = "completed"

    def fail(self, error: str) -> None:
        with self._lock:
            self._result = None
            self._error = error
            self._status = "failed"
            self._phase = "failed"

    def snapshot_after(self, last_event_id: int) -> EventGenerationSnapshot:
        with self._lock:
            return EventGenerationSnapshot(
                status=self._status,
                phase=self._phase,
                chunks=tuple(
                    (event_id, chunk)
                    for event_id, chunk in self._chunks
                    if event_id > last_event_id
                ),
                result=self._result,
                error=self._error,
            )


class EventGenerationCoordinator:
    def __init__(self):
        self._lock = threading.Lock()
        self._current: Optional[EventGenerationOperation] = None

    def get_or_create(
        self, key: EventGenerationKey
    ) -> tuple[EventGenerationOperation, bool]:
        with self._lock:
            current = self._current
            if current is not None and current.status == "running":
                if current.key != key:
                    raise EventGenerationConflict(
                        f"generation already running for {current.key}"
                    )
                return current, False
            if current is not None and current.key == key and current.status == "completed":
                return current, False
            operation = EventGenerationOperation(key)
            self._current = operation
            return operation, True
```

In `GameLoopSession.__slots__`, replace the unused `_is_generating` slot with `event_generation`, initialize it with `EventGenerationCoordinator()`, and remove `try_start_generating()` / `finish_generating()`. Do not change `sse_cache`; choice and regenerate streams still use it.

- [x] **Step 4: Run the operation tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_event_generation_contract.py -q
```

Expected: all operation ownership, conflict, retry, and replay tests pass.

- [x] **Step 5: Commit the operation state unit**

```bash
git add src/api/services/event_generation_operation.py src/api/session_store.py tests/test_event_generation_contract.py
git commit -m "feat(gameplay): add durable event generation operation"
```

---

### Task 2: Detach the Generation Worker from SSE Connections

**Files:**
- Modify: `src/api/routers/gameplay/sse_helpers.py`
- Modify: `src/api/routers/gameplay/events.py`
- Modify: `src/game/round/event_generator.py`
- Modify: `tests/test_event_generation_race_db.py`
- Modify: `tests/test_events_router.py`
- Modify: `tests/test_api_gameplay.py`

**Interfaces:**
- Consumes: `session.event_generation.get_or_create(key)` from Task 1.
- Produces: `build_event_generation_key(game_id, game_loop)`.
- Produces: `get_or_start_round_event_generation(game_loop, game_id, session)`.
- Produces: `stream_round_event()` as a subscriber over the durable operation.
- Produces: `wait_for_event_generation(operation, timeout)` for the sync endpoint; timeout disconnects the waiter but does not cancel the job.

- [x] **Step 1: Write a failing disconnect/reconnect integration test**

Replace the timeout-reset tests in `tests/test_event_generation_race_db.py` with a real operation-lifetime test. Use a `threading.Event` to keep the generator running, close the first async generator, then attach a second subscriber:

```python
@pytest.mark.asyncio
async def test_disconnect_does_not_start_a_second_generation():
    import threading

    from src.ai.models import EventOption, GameEvent
    from src.api.routers.gameplay.sse_helpers import stream_round_event
    from src.api.session_store import GameLoopSession

    release = threading.Event()
    started = threading.Event()
    game_loop = MagicMock()
    game_loop.player_state.week = 3
    game_loop.player_state.current_round = 1
    game_loop.current_event = None

    event = GameEvent(
        event_description="同一个后台任务完成的故事",
        options=[EventOption(text="继续", effects={})],
    )

    def generate_round_event(*, stream_callback, status_callback, session):
        started.set()
        status_callback("generating_story")
        stream_callback("同一个后台任务")
        release.wait(timeout=2)
        stream_callback("完成的故事")
        game_loop.current_event = event
        return event

    game_loop.generate_round_event.side_effect = generate_round_event
    session = GameLoopSession(game_loop=game_loop, game_id=91)

    first = stream_round_event(game_loop, 91, session=session)
    await anext(first)
    assert started.wait(timeout=1)
    await first.aclose()

    second = stream_round_event(game_loop, 91, session=session, last_event_id=0)
    release.set()
    payload = "".join([chunk async for chunk in second])

    assert game_loop.generate_round_event.call_count == 1
    assert "完成的故事" in payload
    assert "event: complete" in payload
```

Add a second test proving two simultaneous subscribers call `generate_round_event` once. Update `tests/test_events_router.py` to assert the router delegates to `stream_round_event` without `_get_game_lock`. Update `tests/test_api_gameplay.py::test_event_sync_generation_in_progress` to expect the sync request to wait for and reuse the current operation rather than relying on stale `game_loop._generating`.

- [x] **Step 2: Run backend generation tests and verify RED**

Run:

```bash
python -m pytest \
  tests/test_event_generation_race_db.py \
  tests/test_events_router.py \
  tests/test_api_gameplay.py -q
```

Expected: disconnect/reconnect test fails because closing the first stream releases ownership and no durable operation is used.

- [x] **Step 3: Implement one durable worker and subscriber streaming**

In `src/api/routers/gameplay/sse_helpers.py`, replace the response-local queue ownership in `stream_round_event()` with these functions:

```python
def build_event_generation_key(game_id: int, game_loop) -> EventGenerationKey:
    player_state = game_loop.player_state
    return EventGenerationKey(
        game_id=game_id,
        week=int(player_state.week),
        round_number=int(player_state.current_round),
        stage="event",
    )


def _run_event_generation_operation(operation, game_loop, game_id: int, session) -> None:
    try:
        event = game_loop.generate_round_event(
            stream_callback=operation.publish_story,
            status_callback=operation.publish_phase,
            session=session,
        )
        if event is None:
            raise RuntimeError("No event returned from event generation")
        _persist_generated_event_state(game_loop, game_id)
        operation.complete(event)
        _trigger_round_illustration_generation(game_loop, game_id, event, stage="event")
    except Exception as exc:
        logger.exception("Event generation operation failed: %s", exc)
        operation.fail(str(exc))


def get_or_start_round_event_generation(game_loop, game_id: int, session):
    key = build_event_generation_key(game_id, game_loop)
    operation, should_start = session.event_generation.get_or_create(key)
    if should_start:
        _get_sse_thread_pool().submit(
            _run_event_generation_operation,
            operation,
            game_loop,
            game_id,
            session,
        )
    return operation, should_start


async def wait_for_event_generation(operation, timeout: float = SSE_STREAM_TIMEOUT):
    deadline = asyncio.get_running_loop().time() + timeout
    while operation.status == "running":
        if asyncio.get_running_loop().time() >= deadline:
            raise asyncio.TimeoutError
        await asyncio.sleep(0.1)
    return operation.snapshot_after(-1)


async def stream_round_event(
    game_loop, game_id: int, session=None, last_event_id: Optional[int] = None
):
    if session is None:
        from src.api.session_store import GameLoopSession

        session = GameLoopSession(game_loop=game_loop, game_id=game_id)

    try:
        operation, should_start = get_or_start_round_event_generation(
            game_loop, game_id, session
        )
    except EventGenerationConflict as exc:
        yield make_sse_event("error", {"error": str(exc)})
        return

    cursor = -1 if last_event_id is None else last_event_id
    last_phase = ""
    last_heartbeat = asyncio.get_running_loop().time()
    yield make_sse_event(
        "status", {"phase": "preparing" if should_start else "resuming"}
    )

    while True:
        snapshot = operation.snapshot_after(cursor)
        if snapshot.phase != last_phase:
            last_phase = snapshot.phase
            yield make_sse_event("status", {"phase": snapshot.phase})
        for event_id, chunk in snapshot.chunks:
            cursor = event_id
            yield make_sse_event("story", chunk, event_id=event_id)

        if snapshot.status == "completed":
            yield make_sse_event("complete", snapshot.result.model_dump())
            return
        if snapshot.status == "failed":
            yield make_sse_event(
                "error", {"error": snapshot.error or "Event generation failed"}
            )
            return

        now = asyncio.get_running_loop().time()
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            last_heartbeat = now
            yield make_sse_event(
                "status", {"phase": snapshot.phase, "heartbeat": True}
            )
        await asyncio.sleep(0.1)
```

This moves persistence and illustration triggering into the one worker so multiple subscribers cannot trigger duplicate side effects.

In `src/api/routers/gameplay/events.py`:

- Remove `_game_locks`, `_locks_lock`, `_get_game_lock`, all `game_loop._generating` timeout logic, and `stream_round_event_with_asyncio_lock` from the GET path.
- Keep the existing-event fast path.
- Always return `stream_round_event(game_loop, game_id, session, last_event_id)` for an unfinished event.
- Make `event-sync` call `get_or_start_round_event_generation()` and `wait_for_event_generation()`. On waiter timeout return HTTP 504 while leaving the operation running; on completed return `snapshot.result.model_dump()`; on failed return HTTP 503 with the operation error.

In `src/game/round/event_generator.py`, replace lines 288-308 with an unconditional concurrency rejection:

```python
if self._generating:
    raise ValueError("Event generation in progress, please wait")
```

Keep explicit cleanup on every success/error return. Do not use elapsed time to clear ownership.

- [x] **Step 4: Run backend generation tests and verify GREEN**

Run:

```bash
python -m pytest \
  tests/test_event_generation_contract.py \
  tests/test_event_generation_race_db.py \
  tests/test_events_router.py \
  tests/test_api_gameplay.py \
  tests/test_sse_helpers.py -q
```

Expected: all tests pass; the disconnect test reports exactly one generator call.

- [x] **Step 5: Commit the durable backend worker**

```bash
git add \
  src/api/routers/gameplay/sse_helpers.py \
  src/api/routers/gameplay/events.py \
  src/game/round/event_generator.py \
  tests/test_event_generation_race_db.py \
  tests/test_events_router.py \
  tests/test_api_gameplay.py \
  tests/test_sse_helpers.py
git commit -m "fix(gameplay): keep event generation alive across reconnects"
```

---

### Task 3: Carry SSE Event IDs Through the Frontend

**Files:**
- Modify: `frontend/src/lib/sse.ts`
- Modify: `frontend/src/__tests__/lib/sse.test.ts`

**Interfaces:**
- Produces: `StreamCallbacks.onEventId?: (eventId: number) => void`.
- Produces: `streamGameEvent(..., { signal, lastEventId })` and a conditional `Last-Event-ID` header.
- Consumed by: Task 4 `useEventGenerator` recovery path.

- [x] **Step 1: Add failing event-ID parsing and request-header tests**

Add focused tests to `frontend/src/__tests__/lib/sse.test.ts`:

```typescript
it('commits numeric SSE ids after delivering their story chunks', async () => {
  const onEventId = jest.fn();
  const onStory = jest.fn();
  mockFetchSSE([
    'id: 4\nevent: story\ndata: "后续片段"\n\n',
    'event: complete\ndata: {"event_description":"完成","options":[{"text":"继续"}]}\n\n',
  ]);

  await streamGameEvent(3, { onEventId, onStory });

  expect(onEventId).toHaveBeenCalledWith(4);
  expect(onStory.mock.invocationCallOrder[0]).toBeLessThan(
    onEventId.mock.invocationCallOrder[0]
  );
  expect(onStory).toHaveBeenCalledWith('后续片段');
});

it('sends Last-Event-ID only for a resume request', async () => {
  mockFetchSSE([
    'event: complete\ndata: {"event_description":"完成","options":[{"text":"继续"}]}\n\n',
  ]);

  await streamGameEvent(3, {}, { lastEventId: 7 });

  expect(global.fetch).toHaveBeenCalledWith(
    '/api/games/3/event',
    expect.objectContaining({ headers: { 'Last-Event-ID': '7' } }),
  );
});
```

- [x] **Step 2: Run the SSE tests and verify RED**

Run:

```bash
cd frontend
npx jest src/__tests__/lib/sse.test.ts --runInBand
```

Expected: TypeScript/Jest fails because `onEventId` and `lastEventId` do not exist.

- [x] **Step 3: Parse IDs and set the resume header**

In `StreamCallbacks`, add:

```typescript
onEventId?: (eventId: number) => void;
```

Keep a pending event ID while parsing the SSE event:

```typescript
if (trimmed.startsWith('id: ')) {
  const eventId = Number.parseInt(trimmed.slice(4), 10);
  pendingEventId = Number.isFinite(eventId) ? eventId : null;
  continue;
}
```

After the associated story `data:` line has been delivered to `onStory`, call `onEventId(pendingEventId)` and clear it. Persisting the cursor after story delivery prevents a hard refresh from skipping a chunk that had not yet reached application state.

Change `streamGameEvent` options and request headers to:

```typescript
options?: { signal?: AbortSignal; lastEventId?: number }

const headers = options?.lastEventId === undefined
  ? undefined
  : { 'Last-Event-ID': String(options.lastEventId) };

const response = await fetchSSEWithRetry(`/api/games/${gameId}/event`, {
  method: 'GET',
  credentials: 'include',
  headers,
  signal: options?.signal,
}, callbacks);
```

- [x] **Step 4: Run SSE tests and type checking**

Run:

```bash
cd frontend
npx jest src/__tests__/lib/sse.test.ts --runInBand
npx tsc --noEmit --strict
```

Expected: both commands exit 0.

Hard-refresh review added a second invariant after the initial transport commit: a saved cursor must always have a matching rendered-story snapshot. Two additional hook tests prove paired restore and safe full replay when only an orphaned cursor exists.

- [x] **Step 5: Commit event-ID transport**

```bash
git add frontend/src/lib/sse.ts frontend/src/__tests__/lib/sse.test.ts
git commit -m "feat(frontend): resume event streams by SSE id"
```

---

### Task 4: Make “Recover Current Progress” Read-Only

**Files:**
- Modify: `frontend/src/hooks/game/useEventGenerator.ts`
- Modify: `frontend/src/__tests__/hooks/useEventGenerator.test.ts`

**Interfaces:**
- Consumes: `onEventId` and `{ lastEventId }` from Task 3.
- Changes: `generateEvent(options?: { resume?: boolean })`; removes `force`.
- Guarantees: `recoverEventGeneration()` reopens the subscriber without clearing story/options or creating a new backend operation.

- [x] **Step 1: Replace the bad recovery test with a failing read-only recovery test**

Replace `recovers from a stuck generation by aborting stale work and forcing a new stream` with:

```typescript
it('recovers by resuming the current stream without clearing visible progress', async () => {
  const abort = jest.fn();
  mockAbortRef.current = { abort } as unknown as AbortController;
  mockGeneratingRef.current = true;
  mockPollingRef.current = true;
  mockPhaseRef.current = 'generating' as Phase;
  useGameStore.setState({
    storyText: '已经显示的故事',
    currentEvent: { story: '已经显示的故事', options: [] },
  } as never);

  (global.fetch as jest.Mock).mockResolvedValue(
    createSSEMockResponse([
      'id: 8\nevent: story\ndata: "后续片段"\n\n',
      'event: complete\ndata: {"event_description":"已经显示的故事后续片段","options":[{"text":"继续","effects":{}}]}\n\n',
    ])
  );

  const { result } = renderHook(() => useEventGenerator(defaultParams));
  await act(async () => { await result.current.recoverEventGeneration(); });

  expect(abort).toHaveBeenCalled();
  expect(mockSetters.setStoryText).not.toHaveBeenCalledWith('');
  expect(mockSetters.setOptions).not.toHaveBeenCalledWith([]);
  expect(global.fetch).toHaveBeenCalledTimes(1);
});
```

Add a second test that first receives `id: 4`, triggers recovery, and asserts the second request contains `{ headers: { 'Last-Event-ID': '4' } }`.

- [x] **Step 2: Run the hook test and verify RED**

Run:

```bash
cd frontend
npx jest src/__tests__/hooks/useEventGenerator.test.ts --runInBand
```

Expected: the test fails because current recovery clears options/story state and uses forced generation.

- [x] **Step 3: Implement resume semantics**

In `useEventGenerator`, persist the last received cursor so a full browser refresh can resume the same operation. Add:

```typescript
const eventCursorStorageKey = gameId === null
  ? null
  : `story101:event-cursor:${gameId}`;
const lastEventIdRef = useRef<number | null>(null);

useEffect(() => {
  if (!eventCursorStorageKey) {
    lastEventIdRef.current = null;
    return;
  }
  const stored = window.sessionStorage.getItem(eventCursorStorageKey);
  const parsed = stored === null ? Number.NaN : Number.parseInt(stored, 10);
  lastEventIdRef.current = Number.isFinite(parsed) ? parsed : null;
}, [eventCursorStorageKey]);
```

Change the generator signature and guards:

```typescript
const generateEvent = useCallback(async (options?: { resume?: boolean }) => {
  const resume = Boolean(options?.resume);

  if (generatingRef.current && !resume) return;
  if (isRetryingRef.current && !resume) return;

  const currentPhase = phaseRef.current;
  if (currentPhase !== 'loading' && currentPhase !== 'error' && !resume) return;
```

For a new attempt, reset the cursor and clear only invalid/failed partial output. For resume, preserve current state:

```typescript
if (!resume) {
  lastEventIdRef.current = null;
  if (eventCursorStorageKey) {
    window.sessionStorage.removeItem(eventCursorStorageKey);
  }
  if (currentPhase === 'error' || !currentEvent?.options?.length) {
    setStoryText('');
  }
}
setPhase('generating');
```

Pass the callback and resume cursor:

```typescript
onEventId: (eventId) => {
  lastEventIdRef.current = eventId;
  if (eventCursorStorageKey) {
    window.sessionStorage.setItem(eventCursorStorageKey, String(eventId));
  }
},
```

In `onComplete`, remove `eventCursorStorageKey` after `handleEventComplete()` succeeds. This prevents the next round from sending a stale cursor while retaining the cursor across a refresh during an unfinished operation.

```typescript
{
  signal: abortRef.current.signal,
  lastEventId: resume && lastEventIdRef.current !== null
    ? lastEventIdRef.current
    : undefined,
}
```

Rewrite `recoverEventGeneration()` so it aborts only the stale browser subscription, resets local connection guards, preserves story/options, keeps the visible phase as generating, and calls:

```typescript
await generateEvent({ resume: true });
```

Do not call `setOptions([])`, do not set phase to `loading`, and do not introduce another timeout that converts a running backend operation into a new attempt.

- [x] **Step 4: Run hook, page, SSE, and type tests**

Run:

```bash
cd frontend
npx jest \
  src/__tests__/hooks/useEventGenerator.test.ts \
  src/__tests__/pages/PlayPage.test.tsx \
  src/__tests__/lib/sse.test.ts --runInBand
npx tsc --noEmit --strict
```

Expected: all focused Jest suites and strict type checking pass.

- [x] **Step 5: Commit read-only recovery**

```bash
git add \
  frontend/src/hooks/game/useEventGenerator.ts \
  frontend/src/__tests__/hooks/useEventGenerator.test.ts
git commit -m "fix(frontend): attach recovery to active event generation"
```

---

### Task 5: Regression Audit and PR Evidence

**Files:**
- Modify: `docs/superpowers/plans/2026-07-10-p1-01-generation-recovery.md` only to check completed steps and record exact results.
- Do not modify files belonging to P1-2 through P1-9.

**Interfaces:**
- Verifies all interfaces and invariants introduced in Tasks 1-4.
- Produces the evidence used in the P1-1 PR description.

- [x] **Step 1: Scan for obsolete forced-restart contracts**

Run:

```bash
rg -n "force: true|elapsed > 60|auto-resetting flag|_get_game_lock|timeout_auto_reset" \
  frontend/src/hooks/game/useEventGenerator.ts \
  frontend/src/__tests__/hooks/useEventGenerator.test.ts \
  src/api/routers/gameplay/events.py \
  src/game/round/event_generator.py \
  tests/test_event_generation_contract.py \
  tests/test_event_generation_race_db.py
```

Expected: no production or test contract remains that force-restarts recovery or clears generation ownership based only on 60 seconds.

- [x] **Step 2: Run the complete focused backend and frontend suites**

Run:

```bash
python -m pytest \
  tests/test_event_generation_contract.py \
  tests/test_event_generation_race_db.py \
  tests/test_events_router.py \
  tests/test_api_gameplay.py \
  tests/test_sse_helpers.py -q

cd frontend
npx jest \
  src/__tests__/lib/sse.test.ts \
  src/__tests__/hooks/useEventGenerator.test.ts \
  src/__tests__/hooks/usePlayGame.phase.test.ts \
  src/__tests__/pages/PlayPage.test.tsx --runInBand
npx tsc --noEmit --strict
```

Expected: all commands exit 0 without unhandled stream rejections.

- [x] **Step 3: Run repository quality gates**

Run from the repository root:

```bash
git diff --check
./test.sh all
```

Expected: both commands exit 0. If an environment prerequisite blocks `./test.sh all`, record the exact command and error separately from the focused code evidence.

Recorded 2026-07-10:

- `git diff --check`: passed.
- `./test.sh preflight`: passed (74 OpenSpec validations, 129 backend gates, and 494 frontend tests).
- The initial `./test.sh e2e` run exposed an unrelated collection-tab click interception
  by the fixed global “音乐和朗读” player. After that external lock/run cleared, the
  fresh required rerun passed completely: 305 core browser tests, 1 membership AI
  music test, 1 character-settings persistence test, 8 story-voice tests, 4 MiniMax
  audio tests, and 28 collection/entity tests. The final Layer e2e result was PASS.

- [x] **Step 4: Browser-smoke the exact production failure path**

Using a local server or an authorized production test account:

1. Start event generation for an unfinished round.
2. Wait for at least one story chunk and record the operation key/server generation count.
3. Click “恢复当前进度” while generation remains active.
4. Confirm the next request sends `Last-Event-ID` and the server logs `resuming`, not a second worker start.
5. Confirm visible story text is not cleared and the final options appear once.
6. Refresh the page during another generation and confirm the same invariant.

Expected evidence: one worker-start log for the operation key, at least two subscriber connections, one final event, no duplicated story chunks, and no second 80-120 second restart.

Recorded 2026-07-10: a real local game reached a long-running second event at 1m36s with cursor `2535`. Clicking “恢复当前进度” preserved the visible partial story, opened a resumed subscriber, delivered the remaining story and all three options in 4.6s, and cleared the stored cursor on completion. The original subscriber had run for 106s, so recovery did not incur another full generation. Browser evidence is stored locally at `docs/qa-evidence/2026-07-10-p1-01/recovery-completed.png` (the evidence directory is intentionally ignored by Git).

- [x] **Step 5: Final commit and PR preparation**

```bash
git status --short
git log --oneline main..HEAD
git diff --stat main...HEAD
```

Expected: only P1-1 implementation, tests, design, and plan files are present. Preserve the unrelated untracked QA report unless it is deliberately added as PR evidence.

Prepare one PR titled `fix(gameplay): make event generation recovery resumable` with:

- P1-1 reproduction and root cause.
- The one-operation lifecycle and `Last-Event-ID` design.
- RED evidence for the old forced-restart contract.
- Focused and full test output.
- Browser evidence showing one worker and multiple subscribers.
- Explicit note that P1-4 exact save-phase recovery remains a separate dependent PR.
