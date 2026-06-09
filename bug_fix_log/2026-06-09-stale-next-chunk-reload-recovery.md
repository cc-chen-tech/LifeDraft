# Fix: stale Next chunk reload recovery - 2026-06-09

## Problem

Production QA found that an existing `story101.live/play` tab could turn blank after a manual ECS deployment. The tab had been loaded before deployment, then opened the friends panel and clicked back.

Evidence:

- `docs/qa-evidence/2026-06-09-heartbeat-0841-production/08-friends-open.png`
- `docs/qa-evidence/2026-06-09-heartbeat-0841-production/09-after-friends-return-blank.png`
- Console errors from the same QA run:
  - stale `_next/static/chunks/*.js` returned `404`
  - script MIME type was `text/plain`, so the browser refused execution
  - stale `_next/static/chunks/*.css` returned an invalid stylesheet MIME type

## Root Cause

Next.js dynamic chunks are build-hashed. After deployment, a browser tab from the previous build can still try to lazy-load old chunk filenames. The ECS deploy replaces the app bundle, so those old chunks are no longer available. Before this fix, the global error reporter only logged the loading error; it did not recover the tab.

## Reproduction Test

Added regression coverage in `frontend/src/__tests__/lib/remote-log.test.ts`:

- stale `/_next/static/` script load failure reloads once
- stale `/_next/static/` stylesheet load failure does not reload repeatedly inside the cooldown window
- unhandled `ChunkLoadError` rejection reloads once

The tests failed before the implementation because `installGlobalErrorReporter` only logged errors.

## Fix

Updated `frontend/src/lib/remote-log.ts` so the global error reporter:

- detects failed script/link assets under `/_next/static/`
- detects `ChunkLoadError`, `Loading chunk`, and dynamic import failure text
- stores a reload timestamp in `sessionStorage`
- falls back to an in-memory timestamp when `sessionStorage` is unavailable
- reloads the page at most once per 60 seconds to avoid refresh loops

## Verification

Commands run:

```bash
cd frontend && npx jest src/__tests__/lib/remote-log.test.ts --runInBand
npm --prefix frontend run test:types
git diff --check -- frontend/src/lib/remote-log.ts frontend/src/__tests__/lib/remote-log.test.ts
```

Results:

- `remote-log.test.ts`: 10 passed
- `test:types`: passed
- `git diff --check`: passed

## Residual Risk

This fix recovers the client by reloading when a stale build asset is detected. It does not retain old Next static assets on the server. A future deploy strategy should still consider static asset retention or a build-version refresh banner for a smoother user experience.
