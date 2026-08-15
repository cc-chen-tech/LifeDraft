## Why

Coverage jobs currently report success even when a constituent coverage command
fails or an expected report is missing. The maintained backend suite now
measures about 35% coverage, so its enforceable floor must reflect the current
truth instead of reviving the obsolete 60% claim.

## What Changes

- Make `./test.sh coverage` return non-zero when either backend or frontend
  coverage fails and report only coverage outputs that actually exist.
- Enforce a 34% floor in the maintained backend coverage runner while retaining
  the frontend Jest global 70% thresholds.
- Run the real frontend coverage command in `Frontend Tests` and fail artifact
  upload when the expected report is absent.
- Remove Codecov uploads and retain backend XML plus frontend Cobertura/HTML as
  repository-owned GitHub artifacts.
- Add no-mock governance tests for failure propagation and missing artifacts.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `test-gates`: Coverage gates gain explicit failure-propagation, threshold,
  and artifact-presence requirements.

## Impact

- Affects `test.sh`, `scripts/run-maintained-backend-tests.sh`, coverage-related
  GitHub Actions workflows, and governance tests.
- Removes the external Codecov upload dependency.
- Does not change product APIs, database schemas, or runtime business logic.
