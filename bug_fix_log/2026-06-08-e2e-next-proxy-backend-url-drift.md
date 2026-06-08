# E2E Next Proxy Backend URL Drift - 2026-06-08

## Problem

`./test.sh e2e` launched the backend on a dynamic worktree-scoped port, but the production-mode Next.js frontend did not receive the matching `BACKEND_URL`.

Browser-side tests could create an active game through `page.request` because the E2E helpers used `E2E_BACKEND_PORT`, while in-page `/api/*` requests still used the API proxy default `http://localhost:8000`.

## Evidence

- `frontend/e2e/4d-resources-visible.spec.ts` redirected from `/play` back to the homepage.
- The page snapshot showed the unauthenticated home screen instead of the play UI.
- The frontend log showed API proxy `ECONNREFUSED` failures for `/api/auth/me` and `/api/games/active`.

## Root Cause

The E2E backend port was exported for Playwright helpers, but `test.sh` did not pass the same port to the Next.js App Router API proxy. The route handler falls back to `BACKEND_URL || http://localhost:8000`, so production-mode E2E used the wrong backend endpoint.

## Fix

`test.sh` now computes `backend_url="http://127.0.0.1:$E2E_BACKEND_PORT"` and passes it as `BACKEND_URL` to both `npm run build` and `npm run start`. It also keeps `NEXT_PUBLIC_API_URL="/api"` so browser code continues to use the local proxy.

## Regression Coverage

Added `tests/test_gate_preflight_no_mock.py::test_e2e_frontend_proxy_targets_dynamic_backend_port`, which fails if the E2E frontend build/start path no longer binds the dynamic backend URL.

## Verification

Targeted verification:

```bash
python -m pytest tests/test_gate_preflight_no_mock.py::test_e2e_frontend_proxy_targets_dynamic_backend_port -q
```

Browser verification:

```bash
npx playwright test e2e/4d-resources-visible.spec.ts --project=core --reporter=list --workers=1 --no-deps
npx playwright test e2e/story-voice-reading.spec.ts --project=core --reporter=list --workers=1 --no-deps
npx playwright test e2e/minimax-story-audio-generation.spec.ts --project=core --reporter=list --workers=1 --no-deps
```

Full gate verification:

```bash
./test.sh preflight
./test.sh e2e
```
