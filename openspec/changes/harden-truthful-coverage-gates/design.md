## Context

The local aggregate coverage command currently continues after failures and
ends on an informational `echo`, which can turn a failed backend or frontend
run into exit code zero. In CI, `Frontend Tests` invokes the aggregate npm test
script with Jest-only flags, so no coverage directory is created, and the
artifact uploader merely warns. The separate coverage workflow uploads to
Codecov with failures disabled, while its maintained backend runner generates
XML without enforcing a floor.

The latest maintained backend suite measures approximately 35% statement
coverage. The frontend already enforces global 70% Jest thresholds.

## Goals / Non-Goals

**Goals:**
- Make every coverage entry point fail when tests, thresholds, or required
  artifacts fail.
- Establish 34% as the honest maintained-backend floor and retain the frontend
  70% floor.
- Make GitHub artifacts and repository thresholds the authoritative evidence.
- Protect the contracts with no-mock tests that execute real shell behavior and
  parse real workflow configuration.

**Non-Goals:**
- Increasing backend coverage in this change.
- Changing the maintained backend test manifest.
- Changing application behavior, APIs, database schemas, or dependencies.
- Reworking test markers, parallelism, E2E sharding, or dependency locking.

## Decisions

- `test.sh` will retain independent backend and frontend exit codes, print only
  report paths that exist, and return failure if either code is non-zero. This
  preserves both runs for complete local diagnostics while preventing false
  success. Its backend stage will use the same maintained runner as CI so the
  aggregate command does not silently select a different legacy suite.
- Frontend coverage entry points will invoke `npm run test:coverage` so Jest
  receives coverage options directly. Reusing `npm test` was rejected because
  it chains multiple npm scripts and forwards flags only to the final script.
- The maintained backend runner will pass `--cov-fail-under=34` while producing
  `coverage.xml`. A 34% floor provides one point of tolerance below the current
  rounded 35% result without claiming the obsolete 60% baseline.
- Workflow artifacts will be uploaded with `if-no-files-found: error`. Codecov
  uploads are removed because a non-authoritative, failure-tolerant external
  upload obscures whether repository-owned evidence exists.
- Governance tests will run shell behavior in real subprocesses and parse YAML
  into data structures. They will avoid mocks, skips, and source-line matching.

## Risks / Trade-offs

- [Coverage rounds near the 34% floor] → Keep the threshold explicit in the
  maintained runner and record the current measured result in this change.
- [Both local coverage stages run even after the first failure] → Preserve this
  intentionally so developers receive both diagnostics in one invocation.
- [Artifact layout drifts] → Fail uploads when expected XML or HTML outputs are
  absent and enforce paths through governance tests.
- [Removing Codecov reduces an external dashboard] → Preserve downloadable XML,
  Cobertura, and HTML reports as workflow artifacts.

## Migration Plan

Deploy as a workflow-and-test-only change. Rollback is a normal commit revert;
no product data or runtime migration is required.

## Open Questions

None.
