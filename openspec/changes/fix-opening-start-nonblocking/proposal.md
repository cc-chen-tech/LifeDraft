## Why

Starting a completed opening story can appear unresponsive for tens of seconds because synchronous image-provider work runs inside async API routes and blocks the single Uvicorn event loop. The opening page also waits to persist continuity only after the user clicks, without an immediate transition state, so otherwise healthy persistence latency is exposed directly to the click.

## What Changes

- Move synchronous image-provider service calls off the asyncio event loop while preserving existing API responses and error mapping.
- Start idempotent opening-continuity persistence as soon as the opening story is complete.
- Give the start action an immediate, duplicate-safe "entering" state and cap click-time waiting for an existing persistence request at two seconds.
- Preserve navigation when persistence fails after one retry, while recording the failure without blocking the user.
- Add concurrency and frontend contract coverage for slow image generation and delayed continuity persistence.

## Capabilities

### New Capabilities
- `nonblocking-image-provider-routes`: Provider-bound image generation does not block unrelated async API traffic.

### Modified Capabilities
- `character-setting-continuity`: Completed opening-story continuity is persisted proactively and the start transition remains responsive when persistence is slow or unavailable.

## Impact

- Backend image routes and their concurrency tests.
- Opening-story page state, persistence timing, and frontend tests.
- No database migration, API response-shape change, or provider dependency change.
