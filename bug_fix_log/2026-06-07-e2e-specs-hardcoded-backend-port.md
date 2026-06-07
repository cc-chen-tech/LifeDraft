# E2E specs hardcoded the default backend port

Date: 2026-06-07

## Problem

After rebasing onto the runtime-isolated E2E harness, `./test.sh e2e` started the backend and frontend successfully on dynamic ports:

```text
后端端口: 18069，前端端口: 19069
```

The core E2E suite then failed immediately with requests to the old default backend address:

```text
apiRequestContext.post: connect ECONNREFUSED ::1:8000
POST http://localhost:8000/api/games
```

This stopped the run after 10 failures and skipped 290 core tests.

## Root Cause

Several `frontend/e2e/*.spec.ts` files defined their own API URL as `http://localhost:8000`. The E2E harness now intentionally selects a per-worktree backend port and exports `E2E_BACKEND_HOST/E2E_BACKEND_PORT`, but those specs bypassed the shared runtime configuration.

## Test Added

Added `test_e2e_specs_do_not_hardcode_default_backend_port` in `tests/test_gate_preflight_no_mock.py`.

The test scans E2E specs and fails if any spec hardcodes `http://localhost:8000` or `http://127.0.0.1:8000`.

## Fix

`frontend/e2e/helpers/auth.ts` now exports the runtime-derived `API_URL`.

All specs that previously hardcoded the backend now import `API_URL` from the helper, so they follow the same `E2E_BACKEND_HOST/E2E_BACKEND_PORT` contract as authentication helpers and Playwright global setup.

## Verification

```bash
python -m pytest tests/test_gate_preflight_no_mock.py::test_e2e_specs_do_not_hardcode_default_backend_port -q
rg -n "http://localhost:8000|http://127\\.0\\.0\\.1:8000" frontend/e2e
```

Result: the new gate passed, and the search found no remaining hardcoded default backend URLs in `frontend/e2e`.
