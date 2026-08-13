## Why

Image generation uses a process-wide executor whose shutdown and recreation behavior affects retries, worker cleanup, and test isolation. A deterministic contract already verifies that lifecycle but is excluded from the maintained backend gate.

## What Changes

- Promote the existing image thread-pool lifecycle contract into both maintained backend workflow selections.
- Verify creation, shutdown-triggered replacement, and repeated shutdown without mocks or external providers.

## Capabilities

### New Capabilities

- `image-thread-pool-lifecycle-gate`: Maintained backend coverage verifies lifecycle behavior for the image executor.

### Modified Capabilities

- `test-gates`: The maintained backend gate includes the deterministic image thread-pool lifecycle contract.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
- Maintained backend test selection and coverage measurement
