## Why

Concurrent `test.sh e2e` runs can currently bypass the repository-wide lock with `TEST_ALLOW_PARALLEL_E2E=1`. That allows separate worktrees to compete for ports, browser processes, CPU, and Next.js runtime resources, producing misleading Chromium and flaky E2E failures.

## What Changes

- Make the repository-wide E2E lock mandatory for every `test.sh e2e` run.
- Record lock ownership so active runs are distinguishable from stale locks.
- Recover locks only when the recorded owner process is no longer alive.
- Release the lock and namespaced backend/frontend runtimes on normal exit and interruption.
- Add non-mocked regression coverage to `test.sh` for lock contention, stale-lock recovery, and interruption cleanup.
- Preserve browser-speech fallback metadata while a voice-reading backend request is pending, eliminating the clean full-suite `none` state flake without changing provider selection.

## Capabilities

### New Capabilities

- `story-voice-loading-fallback`: Browser-capable clients prepare visible fallback state immediately while authenticated audio resolution remains pending.

### Modified Capabilities

- `test-gates`: E2E gates must serialize across worktrees, reject unsafe parallel bypass, and safely recover stale lock state.

## Impact

- `test.sh` E2E orchestration and cleanup behavior.
- Frontend story voice store loading-state behavior.
- Test-gate contract coverage under `tests/`.
- OpenSpec test-gates requirements. No product API or persisted application data changes.
