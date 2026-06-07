# E2E lock failed when the runtime directory was absent

Date: 2026-06-07

## Problem

After rebasing onto the latest `main`, a fresh `./test.sh e2e` run exited before starting the backend:

```text
另一个 E2E 运行已持有锁，当前运行将退出：/private/tmp/story2-main-verify/.test-runs/locks/e2e.lock
```

There was no real stale lock. The `.test-runs` runtime directory had not been created yet.

## Root Cause

`with_e2e_lock` attempted to create `$TEST_LOCK_DIR/e2e.lock` before ensuring that `$TEST_LOCK_DIR` existed. When the parent directory was missing, `mkdir "$lock_dir"` failed, and the script reported the failure as a lock contention.

This made a clean worktree look like another E2E process was holding the lock.

## Test Added

Added `test_e2e_lock_initializes_lock_directory_before_acquire` in `tests/test_gate_preflight_no_mock.py`.

The test asserts that `test.sh` creates `$TEST_LOCK_DIR` before trying to create the `e2e.lock` directory.

## Fix

`with_e2e_lock` now runs:

```bash
mkdir -p "$TEST_LOCK_DIR"
```

before `mkdir "$lock_dir"`.

## Verification

```bash
python -m pytest tests/test_gate_preflight_no_mock.py::test_e2e_lock_initializes_lock_directory_before_acquire -q
python -m pytest tests/test_gate_preflight_no_mock.py::test_playwright_log_tempfile_template_has_enough_random_suffix tests/test_gate_preflight_no_mock.py::test_e2e_gate_does_not_reuse_frontend_from_other_worktree tests/test_gate_preflight_no_mock.py::test_e2e_local_backend_and_browser_launch_are_configurable tests/test_gate_preflight_no_mock.py::test_e2e_backend_sets_required_jwt_secret tests/test_gate_preflight_no_mock.py::test_e2e_backend_start_waits_for_health_endpoint tests/test_gate_preflight_no_mock.py::test_e2e_lock_initializes_lock_directory_before_acquire tests/test_gate_preflight_no_mock.py::test_e2e_prod_frontend_start_waits_until_listening_in_ci tests/test_gate_preflight_no_mock.py::test_e2e_prod_frontend_start_uses_http_readiness_in_ci -q
```

Result: the focused test passed, then the related E2E runtime gate group passed with 8 tests.
