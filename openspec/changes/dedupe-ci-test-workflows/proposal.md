## Why

Pull requests currently run overlapping frontend Jest suites in three workflow jobs, while the expensive browser workflow starts without a fast repository-wide gate. Repeated pushes also leave obsolete PR runs consuming capacity, but main-branch runs must remain intact because production deployment is pinned to a specific SHA.

## What Changes

- Add `./test.sh quick` as the public fast gate for strict backend static checks, the maintained backend suite, strict TypeScript, and the existing preflight Jest regressions.
- Run the quick gate in the PR E2E job before browser installation and execution, while skipping it for main pushes.
- Make `Frontend Tests` the only workflow that runs the complete frontend Jest suite, owns coverage, and uploads its artifact; keep only the bounded preflight Jest subset inside the PR E2E quick gate.
- Update the production deployment workflow list to match the remaining workflows.
- Add PR-aware concurrency to every non-deployment workflow so obsolete PR runs cancel while each main SHA has an independent non-cancelling group.
- Add static and shell governance regressions for command failure propagation and workflow ownership.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-gates`: Define the public quick gate, unique frontend coverage ownership, PR E2E ordering, deployment workflow consistency, and PR-only cancellation policy.

## Impact

Affected areas are `test.sh`, non-deployment GitHub Actions workflows, the production deployment workflow allowlist, governance tests, and test documentation. Product APIs, database schema, application behavior, and main deployment cancellation semantics are unchanged.
