## Why

The repository has strong local gates for recent changes, but coverage reporting and full-suite health now tell conflicting stories: maintained backend coverage passes quickly at low measured coverage, while the full backend suite reports higher coverage but contains many stale failures. This makes it too easy to misread test health, merge readiness, and the value of new coverage.

## What Changes

- Define explicit maintained-gate and full-suite coverage semantics so CI names, scripts, and reports describe what they actually prove.
- Add test contracts that prevent `test.sh`, GitHub Actions, and coverage commands from drifting apart when new gate tests are introduced.
- Triage stale backend tests into actionable buckets: restore production behavior, update obsolete contracts, or exclude from maintained gates with an explicit reason.
- Add focused coverage for high-risk state-machine paths that recently changed, especially story voice reading, scene image state, and music queue behavior.
- Introduce enforceable coverage thresholds in stages: maintained-gate thresholds first, full-suite thresholds only after full backend health is restored.
- Reduce noisy unit-test output where it obscures failures, without hiding intentional error-path assertions.

## Capabilities

### New Capabilities
- `test-gate-fidelity`: Contracts for maintained gates, coverage reporting, stale-test triage, and high-risk coverage expectations.

### Modified Capabilities

## Impact

- `test.sh` coverage and gate commands.
- GitHub Actions coverage/backend/frontend test workflows.
- Backend pytest coverage selection and stale-contract handling.
- Frontend Jest coverage for story voice, scene image, and music state paths.
- OpenSpec validation expectations for future changes that add tests to `test.sh`.
