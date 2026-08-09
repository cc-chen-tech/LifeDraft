## Why

The current main baseline has materially different coverage health on each side
of the application: frontend Jest coverage already exceeds 70% for lines,
statements, functions, and branches, while the maintained backend selection
passes 243 tests but covers only 32% of `src`. Treating those as one uniform
70% target would either weaken the meaning of the backend metric or create an
unreviewable, test-only mega-change.

## What Changes

- Raise the frontend global coverage gate to the independently measured 70%
  floor for lines, statements, functions, and branches.
- Add deterministic, narrowly scoped backend contracts for high-risk gameplay,
  collection, world-model, and image/illustration paths that currently have
  very low source coverage.
- Promote only stable, no-provider test additions into the maintained backend
  workflow, keeping its selection identical in coverage and backend-test jobs.
- Record the full-backend 70% goal as a phased metric: current full `src`
  coverage is measured on every batch, but the global backend gate is raised
  only after the corresponding deterministic tests exist and pass repeatedly.

## Capabilities

### New Capabilities
- `coverage-ratchet`: Establish separately measured frontend and backend
  coverage floors, with evidence-based ratcheting for backend test additions.
- `high-risk-backend-contract-coverage`: Add stable tests for high-risk
  backend state, response-shape, fallback, and persistence behavior.

### Modified Capabilities
- `test-gates`: Require frontend coverage gates to enforce all four 70% global
  metrics and require promoted backend suites to preserve workflow parity.

## Impact

- `frontend/jest.config.js` will enforce the current verified 70% frontend
  floor.
- New backend tests will target `src/game`, `src/services`, and gameplay SSE
  helpers without production changes or external providers.
- `.github/workflows/coverage.yml` and `.github/workflows/backend-tests.yml`
  may gain only stable selected test files, always in lockstep.
- The branch will report the full backend `src` metric separately from the
  maintained selection so a 70% claim remains technically meaningful.
