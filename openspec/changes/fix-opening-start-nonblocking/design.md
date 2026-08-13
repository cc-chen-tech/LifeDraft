## Context

Production runs one Uvicorn worker. Several `async def` image routes call synchronous provider methods directly, so a slow image request monopolizes the event loop and delays unrelated requests such as the opening-continuity PATCH. The opening page currently starts that PATCH only after the user clicks and exposes the entire wait without a pending state.

## Goals / Non-Goals

**Goals:**
- Keep the async event loop responsive while image providers are slow.
- Persist completed opening continuity before the user asks to enter play.
- Make the start action duplicate-safe, visibly pending, and bounded to two seconds.
- Preserve current response schemas, error mapping, ownership checks, and save semantics.

**Non-Goals:**
- Replacing the image provider, adding a durable image job queue, or changing image quality.
- Changing story-length validation, round generation, or summary behavior.
- Changing the character-settings persistence schema.

## Decisions

### Offload provider-bound service methods at the route boundary

Async image routes will invoke synchronous provider methods through Starlette's `run_in_threadpool`. Local ownership checks and response serialization remain in the route. This follows the existing round-scene generation pattern and avoids a larger service rewrite.

The batch-character route will also await each provider call in the thread pool; its existing async rate-limit sleeps remain non-blocking. Background scene generation already owns a dedicated thread and database session and will remain unchanged.

Alternative considered: convert the entire routes to synchronous `def`. Rejected because several routes intentionally await async sleeps or SSE behavior, and a focused boundary wrapper is easier to verify without changing dependency scheduling.

### Treat opening persistence as one idempotent in-flight operation

The opening page will keep a ref to the latest persistence operation keyed by game id and final story text. Completion of either a newly streamed or restored opening starts persistence. Repeated completion and repeated clicks reuse the same promise rather than issuing duplicate PATCH requests.

If the first PATCH rejects, one retry is issued. The operation resolves to a status instead of leaking an unhandled rejection.

### Bound click-time waiting without cancelling persistence

The start handler immediately sets `isStarting`, disables the completion gate, and races the persistence operation against a two-second timer. The timer does not abort the PATCH; navigation proceeds while the in-flight request is allowed to finish. This avoids the continuity loss caused by cancelling a slow but healthy save.

If persistence already completed, navigation occurs immediately. If both attempts fail before the deadline, navigation still occurs and a structured warning is logged.

### Keep the completion gate accessible

`OpeningCompletionGate` will receive a pending flag, expose `aria-busy`, disable duplicate activation, and render `正在进入…` with a spinner while pending. Its existing backend/visible-completion gate remains authoritative.

## Risks / Trade-offs

- [Thread-pool saturation under many image requests] → Only provider-bound work is offloaded; existing provider rate limits remain, and concurrency behavior is covered without adding a new queue in this change.
- [Navigation can win the two-second race before persistence] → Persistence starts at story completion, continues after navigation, and retries once.
- [A restored opening may trigger a redundant PATCH] → Deep-merge persistence is idempotent and the page-level key prevents duplicates during one mount.
- [SQLAlchemy session used inside a worker thread] → This matches the existing proven round-scene route pattern; tests cover request completion and concurrent API responsiveness.

## Migration Plan

1. Deploy backend thread-pool changes and frontend pre-persistence together.
2. Exercise a delayed image provider while polling health and character-settings PATCH.
3. Confirm start-button pending state and navigation timing with completed and delayed persistence.
4. Roll back the release if image-route error rates or persistence failures rise; no stored-data migration is involved.

## Open Questions

None.
