# E2E backend startup readiness was flaky

Date: 2026-06-07

## Problem

After fixing API contract failures, a fresh `./test.sh e2e` run sometimes stopped before Playwright with:

```text
后端启动失败，跳过 E2E 测试
```

The backend log did not contain an application traceback, and the same backend command could start successfully when run directly.

## Root Cause

`test.sh` started the E2E backend, slept for a fixed 3 seconds, and then checked the port with `lsof`. Immediately after cleaning up a previous backend process, startup can take longer than the fixed delay or the port can briefly remain unavailable. The script also set `E2E_BACKEND_HOST/E2E_BACKEND_PORT`, but `run_api.py` reads `API_HOST/API_PORT`.

This made local E2E verification flaky and could hide the actual product failures behind a harness startup failure.

## Test Added

Added `test_e2e_backend_start_waits_for_health_endpoint` in `tests/test_gate_preflight_no_mock.py`.

The test asserts that `test.sh`:

- starts `run_api.py` with `API_HOST=127.0.0.1 API_PORT="$E2E_BACKEND_PORT"`,
- waits for `GET /api/health` on the selected E2E backend port,
- prints `$BACKEND_LOG` on startup failure,
- avoids the fixed `sleep 3` plus `lsof` startup gate.

## Fix

`run_e2e_browser` now starts the backend with the `API_HOST/API_PORT` variables consumed by `run_api.py`, waits up to 30 seconds for `/api/health` on the selected E2E backend port, and checks whether the backend process exited early.

On failure, it prints the backend log and terminates any leftover backend process.

## Verification

```bash
python -m pytest tests/test_gate_preflight_no_mock.py::test_e2e_backend_start_waits_for_health_endpoint tests/test_gate_preflight_no_mock.py::test_e2e_backend_sets_required_jwt_secret -q
bash -n test.sh
```

Result: both checks passed.
