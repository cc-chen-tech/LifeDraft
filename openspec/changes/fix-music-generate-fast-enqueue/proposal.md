## Why

The 2026-06-08/2026-06-09 UX report observed `/api/music/generate` taking 8s+ and surfacing as an AbortError while the player fell back to NetEase recommendations. The root cause is that the synchronous route calls `StoryMusicGenerationService.generate_ready_track()` directly. Real MiniMax music generation can take much longer than an interactive HTTP request should hold open, so the route behaves like a blocking generation job instead of a non-blocking gameplay supplement.

## What Changes

- Keep deterministic local-audio mode synchronous so existing contract and E2E tests can still verify ready generated tracks.
- Make the real MiniMax provider path for `/api/music/generate` enqueue generation in the background and return HTTP 202 immediately.
- Preserve the existing `/api/music/generate-async` behavior and future-queue insertion policy.
- Update generated OpenAPI types so frontend consumers can see that `/api/music/generate` may return either a ready track or a queued response.

## Impact

- Backend music API route: `src/api/routers/music.py`.
- MiniMax music contract tests: `tests/test_minimax_audio_generation_contract.py`.
- Generated OpenAPI schema/types: `frontend/src/types/openapi-schema.json`, `frontend/src/types/api-generated.d.ts`.
