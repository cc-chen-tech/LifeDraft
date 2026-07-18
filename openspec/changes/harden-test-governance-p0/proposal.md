## Why

The maintained backend test set is duplicated across CI workflows, while the
preflight OpenAPI check writes generated files into the active worktree. These
conditions create drift and make a test command appear to modify product
sources. The browser gate also reruns core Playwright specs after already
executing the core project, increasing runtime and flake exposure without
adding coverage.

## What Changes

- Make one repository script the authoritative maintained-backend test manifest
  for both the normal and coverage CI gates.
- Make the OpenAPI drift check generate schema and TypeScript declarations in a
  per-run temporary directory, then compare them with the tracked artifacts.
- Run each Playwright spec at most once in the default browser gate while
  preserving the selected high-risk browser checks.
- Add regression tests that enforce these test-runner contracts and exclude
  frontend test helpers from production coverage collection.

## Capabilities

### New Capabilities
- `hermetic-test-gates`: Maintained CI gates and local preflight checks are
  reproducible, single-sourced, and leave tracked files unchanged.
- `nonduplicated-browser-gate`: The default browser gate has explicit,
  non-overlapping Playwright execution stages.

### Modified Capabilities
- None.

## Impact

- Affects `test.sh`, GitHub Actions workflows, Jest coverage configuration, and
  test-runner helper scripts.
- Does not change production APIs or runtime behavior.
