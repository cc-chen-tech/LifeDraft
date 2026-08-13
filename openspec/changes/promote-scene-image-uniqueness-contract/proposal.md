## Why

Scene-image retry and SSE delivery tests assume that one game stage maps to one persisted image record. The model-level uniqueness invariant already has a deterministic, dependency-free contract test, but it is not part of the maintained backend gate.

## What Changes

- Promote the existing SceneImage composite unique-index contract into both maintained backend workflow selections.
- Require the maintained gate to verify the exact `(game_id, week, round_number, stage)` index columns and their order.

## Capabilities

### New Capabilities

- `scene-image-uniqueness-gate`: Maintained backend coverage verifies the scene-image persistence key is unique and ordered.

### Modified Capabilities

- `test-gates`: The maintained backend gate includes the deterministic SceneImage uniqueness contract.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
- Maintained backend test selection and coverage measurement
