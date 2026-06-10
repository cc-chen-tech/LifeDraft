## Why

Recent production and QA regressions are concentrated in implicit data-contract behavior:
new fields, empty/nullable edge values, retry semantics, and async side-effect paths in gameplay/image/collection/session flows.
Current tests cover happy paths well, but several edge contracts remain untested, which increases regression risk while coverage is still below target.

## What Changes

- Add backend contract tests for high-risk gameplay session and SSE paths:
  - `src/game/historical_summary_selector.py`
  - `src/game/narrative_manager.py`
  - `src/api/routers/gameplay/sse_helpers.py`
  - `src/api/services/session_service.py`
- Add focused contract tests for field/shape defaults and boundary values that were recently involved in stateful bugs.
- Keep all additions in new test files; do not modify existing test files.

## Capabilities

### New Capabilities
- `field-contract-hardening`: Add contract-focused tests that define required behavior for gameplay, SSE, and session-service field/state boundaries.

### Modified Capabilities
- _None (test-only coverage additions; no existing specification change)_

## Impact

- Backend gameplay/session modules and SSE helpers will gain stronger contract coverage.
- Safer pre-merge signals for regressions that manifest before full browser/e2e verification.
- No direct production code behavior changes in this change; coverage only.
