# Preflight gates still expected old E2E runtime paths

Date: 2026-06-07

## Problem

After rebasing onto latest `main`, `./test.sh all` failed during preflight with stale gate assertions in `tests/test_gate_preflight_no_mock.py`.

The failing tests still expected:

- a `/tmp/story2-playwright-*` `mktemp` log pattern,
- the removed `ensure_e2e_frontend_port_available` guard,
- a fixed `/tmp/frontend_e2e.log` frontend log path.

## Root Cause

Latest `main` had moved E2E runtime state into a per-worktree `.test-runs` directory with dynamic backend/frontend ports and per-run log paths. The preflight gates were not fully updated to assert the new runtime isolation contract.

## Test Reproduction

```bash
python -m pytest tests/test_gate_preflight_no_mock.py::test_playwright_log_tempfile_template_has_enough_random_suffix tests/test_gate_preflight_no_mock.py::test_e2e_gate_does_not_reuse_frontend_from_other_worktree tests/test_gate_preflight_no_mock.py::test_e2e_prod_frontend_start_waits_until_listening_in_ci -q
```

Before the fix, all three tests failed against the latest `test.sh`.

## Fix

Updated the gates to assert the current runtime contract:

- Playwright logs are written under `$PLAYWRIGHT_LOG_DIR` with timestamp and `$RANDOM` suffix.
- The frontend port is selected through `find_free_port "$E2E_FRONTEND_PORT"` and `TEST_E2E_FRONTEND_PORT_BASE`.
- Startup failure prints `$FRONTEND_LOG`.

## Verification

```bash
python -m pytest tests/test_gate_preflight_no_mock.py::test_playwright_log_tempfile_template_has_enough_random_suffix tests/test_gate_preflight_no_mock.py::test_e2e_gate_does_not_reuse_frontend_from_other_worktree tests/test_gate_preflight_no_mock.py::test_e2e_prod_frontend_start_waits_until_listening_in_ci -q
```

Result: 3 passed.
