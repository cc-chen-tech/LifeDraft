## Context

`test.sh` already namespaces databases, logs, PID files, and preferred ports by worktree path, and it normally serializes E2E runs with a lock under the shared test runtime root. The lock can still be bypassed with `TEST_ALLOW_PARALLEL_E2E=1`, and its directory contains no owner metadata. An interrupted shell can therefore leave an unidentifiable stale lock, while an opted-out run can race another worktree for host-level browser and runtime resources.

Clean-room diagnosis used a dedicated SQLite database and dedicated ports with the repository `.env`. The browser-speech fallback passed 20 consecutive repetitions, and the complete voice-reading spec passed 5 consecutive repetitions (40 tests). A later full clean E2E run reproduced one guest voice failure after sustained suite load: the store remained in `playbackMode=none` for five seconds while awaiting protected settings/read requests, then passed on retry. This separates two causes: unsafe parallel execution is an environment isolation bug, while clearing prepared browser fallback metadata during backend loading is a frontend timing bug.

## Goals / Non-Goals

**Goals:**

- Guarantee that only one repository E2E gate owns shared host resources at a time.
- Fail clearly when callers request the unsafe parallel bypass.
- Attach PID, namespace, and project metadata to the lock.
- Reclaim a stale lock only after proving its owner PID is not alive.
- Release runtimes and lock ownership on success, failure, `SIGINT`, and `SIGTERM`.
- Exercise the real shell lock behavior from a non-mocked pytest included in `test.sh preflight`.
- Keep browser fallback mode and story text observable immediately while backend audio resolution is pending.

**Non-Goals:**

- Parallelizing the E2E suite across worktrees.
- Changing Playwright browser selection, provider selection, or when speech/audio playback actually starts.
- Killing processes that are not recorded in the current namespace PID files.
- Loading production database configuration into E2E; E2E continues to override the database with its isolated SQLite path.

## Decisions

### Keep a mandatory repository-wide lock

All E2E calls continue to use one lock under `TEST_RUN_ROOT/locks`. `TEST_ALLOW_PARALLEL_E2E=1` becomes an explicit error instead of a bypass. This is preferred over per-worktree locks because Chromium, CPU, and port allocation remain host-level shared resources even when build and data files are namespaced.

### Store and verify lock ownership

After atomically creating the lock directory, the owner writes its shell PID, project path, and namespace through an atomic owner-file rename. A contender checks the PID with `kill -0`. A live owner causes a fail-fast contention error. A newly created ownerless lock is preserved because owner publication may still be in progress; only an ownerless lock older than one minute or a lock with a dead owner PID permits an atomic stale-lock rename followed by one acquisition retry. The owner removes the lock only when the stored PID still matches its own PID.

### Make `test.sh` sourceable for real lock tests

The command dispatcher will run only when `test.sh` is executed directly. Regression tests can therefore source the actual lock functions in child shells, hold a real lock, send real signals, and inspect real filesystem state without starting the full application or mocking shell behavior.

### Preserve fail-fast behavior

Contenders do not wait indefinitely. CI and local callers receive a non-zero result with owner details so orchestration can retry deliberately rather than hanging.

### Prepare browser fallback metadata without starting duplicate playback

When browser speech APIs are present, `startReading` records `browser_speech`, the story text, and its length in the initial loading state instead of clearing them to `none`, empty text, and zero. It does not call `speechSynthesis.speak` at that point. A ready backend asset still replaces the prepared metadata with audio state; a 401 or backend failure calls the existing browser-speech start path. This removes the visible indeterminate state without racing MiniMax audio against active browser speech.

When the caller explicitly selects the browser provider, provider resolution is already complete. The client starts browser speech as soon as the real backend recording request is dispatched, then treats its response as bookkeeping and does not start speech a second time. This preserves the request contract while removing an unnecessary backend latency dependency from playback.

## Risks / Trade-offs

- [Long E2E run blocks other worktrees] -> Fail fast with owner metadata and keep the existing explicit serialization contract.
- [PID reuse could misclassify an old lock as live] -> Record project and namespace for diagnosis; never delete a lock while its PID is alive.
- [Two contenders race to reclaim one stale lock] -> Use an atomic rename to a contender-specific stale path; only the rename winner retries acquisition.
- [Contender observes the lock before owner publication] -> Preserve ownerless locks for a one-minute initialization grace period.
- [Signal cleanup removes another owner's lock] -> Release only when the owner file still contains the current shell PID.
- [Prepared fallback could be mistaken for active speech] -> Keep `readingState=loading`; only the existing fallback path changes it to `playing` and invokes speech synthesis.

## Migration Plan

1. Add regression tests and observe failures against the current bypass and ownerless lock.
2. Implement owner-aware mandatory locking and signal cleanup.
3. Reproduce the full-suite voice timing failure, implement prepared fallback metadata, then run targeted tests, OpenSpec strict validation, all non-browser gates, repeated voice E2E, and the complete `test.sh all` gate.
4. Roll back by reverting this change; no application data migration is required.

## Open Questions

None.
