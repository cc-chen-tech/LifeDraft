## Context

`Frontend Tests`, `Frontend Integration Tests`, and the frontend job in `Coverage Report` all install the same dependencies and execute overlapping Jest suites. The E2E workflow installs both Python and Node dependencies but starts Playwright without first exercising the fast static and maintained suites. All non-deployment workflows accept both PR and main events without concurrency controls, so stale PR commits continue running alongside their replacements.

The production deployment workflow polls a hard-coded list of workflow names for one main SHA. Workflow deletion therefore has to update that list atomically. Main runs cannot be cancelled because the E2E completion event selects the SHA that production deploys.

## Goals / Non-Goals

**Goals:**

- Provide one stable local command for the fast pre-browser gate.
- Reuse the current strict/static, maintained backend, TypeScript, and preflight Jest authorities without weakening them.
- Keep one complete frontend Jest/coverage workflow and one required frontend artifact while allowing the bounded preflight Jest subset in quick.
- Cancel superseded PR runs while allowing every main SHA run to finish.
- Keep the deployment workflow list synchronized with actual non-deployment workflow names.

**Non-Goals:**

- Changing pytest markers, browser sharding, dependency locking, formatter behavior, or coverage thresholds.
- Changing the E2E test implementation or production deployment command.
- Cancelling main workflow or deployment runs.

## Decisions

### Compose quick from existing gate functions

`run_quick` will call four named helpers in order: the existing strict mypy/static gate, the maintained backend runner, strict TypeScript, and the existing preflight Jest collection. The TypeScript and Jest blocks will be extracted from preflight into shared functions so the file lists and flags cannot drift. The command will run every sub-gate, aggregate failures, and return non-zero if any sub-gate fails.

### Gate PR E2E before installing browsers

The E2E job already owns the Python and Node dependency environment needed by quick. A pull-request-only step will run `./test.sh quick` after dependencies and test environment setup but before Playwright browser installation. Main pushes skip the extra step to avoid extending the deployment critical path.

### Assign frontend coverage to Frontend Tests

`Frontend Tests` will be the only owner of the complete Jest suite, coverage thresholds, and coverage artifact. It will keep the repository's 70% Jest thresholds and produce text, Cobertura, and HTML reports. The frontend coverage job in `Coverage Report` and the entire integration workflow will be removed; the existing coverage command already discovers both unit and integration Jest tests. The E2E quick gate may still execute the explicitly bounded preflight Jest collection, which is not a second complete-suite or coverage authority.

### Use one PR-aware concurrency expression

Every non-deployment workflow will use the workflow name plus PR number for pull requests or the unique commit SHA for other events. `cancel-in-progress` will evaluate true only for pull requests. Main pushes therefore have independent groups and retain every SHA's deployment evidence; using the shared main ref was rejected because GitHub may replace an older pending run even when `cancel-in-progress` is false.

### Treat workflow files as the deployment allowlist source of truth

The production required-workflow array will remove `Frontend Integration Tests` and otherwise match all remaining non-deployment workflow names. A governance test will compare those sets directly.

## Risks / Trade-offs

- [Quick adds work before PR E2E] -> It reuses dependencies already installed in the same job and prevents the much more expensive browser phase from starting on basic failures.
- [Deleting the integration workflow could hide a suite] -> `npm run test:coverage` runs Jest without path exclusions and remains guarded by the existing global 70% thresholds.
- [Concurrency expressions can accidentally cancel main] -> Static tests require the exact PR-only boolean expression in every non-deployment workflow.
- [Shared preflight helpers can change legacy behavior] -> Preflight and quick call the same extracted functions, and the complete local gate verifies both paths.

## Migration Plan

Land the CLI, workflow deletion, workflow edits, deployment allowlist update, and governance tests together. Rollback is a single revert; no persistent state or external service migration is required.

## Open Questions

None.
