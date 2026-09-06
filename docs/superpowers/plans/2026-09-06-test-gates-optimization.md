# Test Gates Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Reduce duplicate CI execution, make test entry points accurately describe their coverage, lower database-fixture overhead, and remove avoidable real-time waits and stale test-status noise while preserving isolation and coverage.

**Architecture:** Keep one authoritative owner for each CI gate. Split runner commands by actual scope (`quick`, `acceptance`, `full-backend`, and E2E projects), and make expensive suites explicit. Refactor pytest isolation in layers: preserve database isolation, but avoid unconditional schema rebuilds where a transaction or targeted reset is sufficient; make timing behavior injectable in tests instead of sleeping against wall-clock time.

**Tech Stack:** Bash, GitHub Actions, pytest, SQLAlchemy/SQLite, FastAPI TestClient, Jest, Playwright.

**Spec:** The approved user request and the preceding test audit, using local `origin/main` commit `34523af3648bdcd75d37b9ec71e97a2283414592` as the baseline.

## Global Constraints

- All work must remain on branch `codex/optimize-test-gates` in `/Users/luicy/story2/.worktrees/optimize-test-gates`.
- Do not modify or import changes from the original checkout or any other active worktree.
- Preserve test isolation; no optimization may allow tests to share database rows or leaked process-global state.
- Keep the existing maintained backend gate and configured Playwright AI-heavy suite available through explicit commands or workflows.
- Use focused test-first verification for behavior changes and run focused tests after each phase before proceeding.

---

### Task 1: Remove duplicate maintained and mypy CI execution

**Files:**
- Modify: `.github/workflows/e2e-tests.yml:42-49`
- Modify: `.github/workflows/backend-tests.yml:37-49`
- Modify: `test.sh:421-486`
- Test: `tests/test_test_runner_contract.py`

**Interfaces:**
- Consumes: existing `run_mypy`, `run_maintained_backend_suite`, and `run_quick` functions.
- Produces: one backend workflow owner for mypy plus the maintained suite; a PR quick gate that does not duplicate those backend tests.

- [ ] **Step 1: Write a failing CI ownership assertion**

Create `tests/test_test_runner_contract.py` with an assertion that the E2E PR quick step invokes a frontend/preflight-only command and that Backend Tests remains the owner of mypy and maintained backend commands.

- [ ] **Step 2: Run the assertion to verify it fails**

Run: `pytest tests/test_test_runner_contract.py -q`

Expected: FAIL because E2E currently invokes `./test.sh quick`, whose implementation includes mypy and maintained backend tests.

- [ ] **Step 3: Implement the ownership split**

Add `run_quick_frontend` containing frontend strict typecheck and preflight Jest. Keep `run_quick` for explicit local callers, but change the E2E workflow PR step to `./test.sh quick-frontend`. Keep Backend Tests as the sole CI owner of `./test.sh mypy` and `./scripts/run-maintained-backend-tests.sh test`.

- [ ] **Step 4: Verify and commit**

Run `pytest tests/test_test_runner_contract.py -q` and `bash -n test.sh`. Then commit with `git commit -m "ci: remove duplicate backend quick gates"`.

### Task 2: Make `all` and E2E coverage boundaries explicit

**Files:**
- Modify: `test.sh` help/dispatch and layered runner
- Modify: `frontend/playwright.config.ts`
- Modify: `frontend/package.json`
- Modify: `.github/workflows/e2e-tests.yml`
- Test: `tests/test_test_runner_contract.py` and Playwright list commands

**Interfaces:**
- Consumes: existing layer functions and Playwright `core`/`ai-heavy` projects.
- Produces: accurately named `acceptance`, `full-backend`, `e2e-core`, and `e2e-full` commands; explicit AI-heavy coverage; preserved HTML report artifact.

- [ ] **Step 1: Add failing command-boundary assertions**

Extend `tests/test_test_runner_contract.py` to require the new command names and reject describing the current 612-item layered selection as full backend coverage.

- [ ] **Step 2: Run the assertion to verify it fails**

Run: `pytest tests/test_test_runner_contract.py -q`. Expected: FAIL against the current `all`/`e2e` naming and dispatch.

- [ ] **Step 3: Implement explicit runner commands**

Rename the current layered behavior to `run_acceptance`, add `run_full_backend` for the complete pytest suite, and retain `all` as a compatibility alias delegating to `acceptance`. Split E2E execution into core and full paths; full runs core, all configured AI-heavy tests, and configured mobile tests when available. Use a reporter setup that writes the HTML report and still emits concise console output.

- [ ] **Step 4: Align npm scripts and CI**

Add explicit frontend scripts for unit, integration, and full E2E selection without relying on nested npm argument forwarding. Run core on PRs and make full AI-heavy execution explicit for scheduled/main-branch coverage while retaining report upload.

- [ ] **Step 5: Verify and commit**

Run the contract test, `bash -n test.sh`, `CI=1 bash test.sh help`, and the two Playwright `--list` commands for `core` and `ai-heavy`. Commit with `git commit -m "test: make acceptance and e2e coverage explicit"`.

### Task 3: Reduce database fixture overhead without weakening isolation

**Files:**
- Modify: `tests/conftest.py`
- Modify: `src/database/models.py` only if a narrowly scoped initialization seam is required
- Modify: selected schema/migration tests only when redundant initialization is proven
- Test: database isolation and module-reset tests

**Interfaces:**
- Consumes: isolated SQLite process database, SQLAlchemy engine/session, and image/SSE cleanup.
- Produces: targeted schema lifecycle fixtures, one background-state restoration fixture, and no cross-module data leakage.

- [ ] **Step 1: Add isolation regression tests**

Add focused tests proving rows do not cross isolation boundaries and `_background_jobs_enabled` is restored after mutation.

- [ ] **Step 2: Run the regression tests before the fixture change**

Run `pytest tests/test_database_runner_isolation_no_mock.py -q` and the new focused tests. Confirm the existing isolation behavior is the baseline.

- [ ] **Step 3: Implement targeted database lifecycle**

Replace unconditional module-wide `drop_all`/`create_all` for ordinary modules with a transaction-safe reset compatible with the SQLite setup. Keep full rebuilds for migration/schema tests and preserve image-cache clearing.

- [ ] **Step 4: Combine duplicate global-state fixtures**

Merge `_restore_sse_background_state` and `_restore_background_job_admission` into one autouse fixture with one documented responsibility and the same post-test restoration.

- [ ] **Step 5: Remove only verified redundant `init_db()` calls**

Retain calls in migration/schema tests; remove only ordinary-test calls that duplicate fixture setup, adding a focused test where lifecycle assumptions change.

- [ ] **Step 6: Verify and commit**

Run the isolation/DB focused tests with warnings enabled and commit with `git commit -m "test: reduce database fixture reset overhead"`.

### Task 4: Replace real-time waits and clean xfail/warning policy

**Files:**
- Modify: opening-story, SSE-timeout, and long-context tests
- Modify: the minimum production timing seam required by those tests
- Modify: stale xfail declarations identified during focused runs
- Modify: `test.sh` unit/slow selectors and help text
- Test: affected modules and marker-selection assertions

**Interfaces:**
- Consumes: existing SSE heartbeat and long-context behavior.
- Produces: deterministic timing tests, fast default unit selection, explicit slow/stress selection, and intentional xfail/skip policy.

- [ ] **Step 1: Write failing timing-seam tests**

Add focused tests for injected heartbeat/clock behavior so the tests can advance time or signal events without wall-clock sleeps.

- [ ] **Step 2: Run them and confirm the expected failure**

Run the new focused tests and confirm they fail because current code hard-codes sleep/timeout behavior.

- [ ] **Step 3: Implement deterministic timing seams**

Inject only the minimum clock/interval or event hook needed by the SSE/opening-story tests, keeping production defaults unchanged. Mark the 600-event long-context test as `slow`.

- [ ] **Step 4: Add explicit fast/slow selection**

Change the unit selector to `-m 'unit and not slow'`, add a `slow` command using `-m slow`, and document that stress tests remain explicitly available.

- [ ] **Step 5: Clean status policy and verify**

Convert stable xpasses into normal tests, make intentional xfails strict, and remove only stale skips after behavior verification. Run the affected modules, collect both marker sets, and commit with `git commit -m "test: make timing gates deterministic"`.

## Final verification

Run:

```bash
git status --short --branch
git log --oneline --decorate -5
bash -n test.sh scripts/run-maintained-backend-tests.sh scripts/run-with-isolated-test-database.sh
/Users/luicy/story2/venv/bin/python -m pytest --collect-only -q --disable-warnings
/Users/luicy/story2/venv/bin/python -m pytest -q --disable-warnings --tb=short
```

Report local test evidence separately from CI status; do not claim CI or deployment completion from local results.
