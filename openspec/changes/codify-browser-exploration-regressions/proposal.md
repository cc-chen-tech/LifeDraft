## Why

Browser-agent and Playwright exploration previously found regressions that were easy to miss with green static, contract, or narrow store tests. The project needs those exploration findings codified into maintained gates so real gameplay regressions do not depend on remembering old reports.

## What Changes

- Add an explicit regression-codification contract for browser exploration findings.
- Extend maintained preflight coverage with tests for previously observed gameplay, history, collection, image, music, and creation-flow regressions.
- Ensure deep browser exploration scripts stay discoverable and are invoked by the maintained no-mock browser gate.
- Preserve the existing full browser sweep as a deeper optional signal, while moving stable findings into faster deterministic tests.

## Capabilities

### New Capabilities
- `browser-regression-codification`: Browser exploration findings that affect gameplay, history, media, collection, music, or creation flow must be represented by maintained deterministic tests.

### Modified Capabilities

None.

## Impact

- Frontend preflight tests under `frontend/src/__tests__/preflight/`.
- Frontend no-mock Playwright regressions under `frontend/e2e/`.
- `test.sh` gate wiring for maintained browser regression coverage.
- OpenSpec change artifacts documenting the exploration-to-test workflow.
