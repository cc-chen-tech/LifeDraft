## Context

Existing image-router coverage verifies persisted image reads and deletes, but the browser-facing local file route, cached scene-image SSE events, and error ownership boundaries remain comparatively weak. The test suite already provides an in-memory SQLite `db_session` fixture and the image storage service supports an isolated file under its configured local path.

## Goals / Non-Goals

**Goals:**
- Exercise local image bytes and response metadata without an HTTP server or provider call.
- Preserve the public SSE payload for a cached event owned by the caller.
- Preserve deterministic 404 authorization and lookup failures using real database rows.
- Keep both maintained workflow test lists identical.

**Non-Goals:**
- Change image route behavior, storage configuration, or error handling.
- Test external image generation providers, browser rendering, or long-lived SSE reconnect behavior.
- Modify existing tests.

## Decisions

- Call route functions directly with a real SQLite session and Starlette request. This follows the existing router contract pattern while avoiding process, port, and auth-token noise.
- Write one uniquely named temporary image beneath the configured local image root, then remove only that file and empty parents. This exercises the real `ImageStorageService` path handling without broad cleanup.
- Publish one event into the existing in-memory cache and consume the response iterator with `once=True`. This verifies the serialized client payload without a timing-dependent long-lived stream.
- Register the focused module in both workflow lists. Maintaining exact list parity prevents the coverage gate and backend test job from silently testing different scopes.

## Risks / Trade-offs

- [Configured local path is shared across worktrees] -> use a deterministic dedicated game directory and remove only the file and empty directories created by the test.
- [The SSE cache is module-global] -> remove the exact event key in `finally` so tests do not leak state.
- [Direct route calls do not verify browser rendering] -> retain browser and end-to-end coverage for overlays, timing, and actual asset loading.

## Migration Plan

No data or runtime migration is needed. The change adds tests and workflow entries only; reverting removes those additions.
