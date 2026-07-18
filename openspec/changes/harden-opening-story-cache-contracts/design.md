## Context

The opening-story endpoint exposes a cache-backed SSE response before it invokes character generation. A current cached result and a fresh in-flight marker are deterministic shared-state boundaries that can be validated without a provider.

## Goals / Non-Goals

**Goals:**
- Verify cache replay emits status, story, and complete SSE frames with cache-control headers.
- Verify a fresh duplicate in-flight request is rejected before generation starts.
- Verify explicit and trivial truncation decisions.

**Non-Goals:**
- Generate an opening story, call a provider, or test heartbeat timing.
- Change cache timeouts or edit existing tests.

## Decisions

- Populate only one exact cache key under the router lock and remove it in `finally`.
- Consume the returned one-shot cached body iterator directly, avoiding an HTTP server and background thread.
- Assert explicit `length`, empty, and too-short cases; the heuristic's long-text language analysis remains covered separately.

## Risks / Trade-offs

- [Cache is process-global] -> remove each test key in `finally`.
- [SSE body chunks can be bytes or strings] -> normalize them before JSON assertions.
- [Live generation remains untested here] -> retain provider/integration coverage for that boundary.

## Migration Plan

No migration is required. This is a test-only change.
