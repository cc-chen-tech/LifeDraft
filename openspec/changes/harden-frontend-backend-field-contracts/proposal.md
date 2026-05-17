## Why

Frontend/backend field drift has already caused browser-visible regressions: mocked frontend responses omitted backend fields, hand-written TypeScript types disagreed with backend payloads, and SSE event payloads were only partially covered. The current gates catch several known cases, but they do not yet make generated API schema, hand-written frontend types, mocks, and stream payloads converge.

## What Changes

- Add a focused field-contract gate for high-risk API surfaces shared by the backend, generated OpenAPI schema, hand-written frontend types, and frontend mocks.
- Convert stale warning/documentation-style field checks into hard assertions where the underlying contract has already been repaired.
- Add SSE payload contract coverage for browser-agent regression surfaces that are not fully represented by OpenAPI.
- Wire the new contract tests into maintained/preflight gates so field drift fails before browser E2E.

## Capabilities

### New Capabilities
- `frontend-backend-field-contracts`: Contract tests and gate wiring that keep critical backend response fields, generated schema, frontend hand-written types, frontend mocks, and SSE payloads aligned.

### Modified Capabilities

## Impact

- Backend test suite: new and/or tightened contract tests under `tests/`.
- Frontend test fixtures/types: validated through source-level and generated-schema assertions.
- CI/local gates: `test.sh preflight`, `test.sh contract`, and maintained backend coverage include the field-contract gate.
- OpenAPI artifacts: generated schema/type synchronization remains enforced and is treated as part of the field contract.
