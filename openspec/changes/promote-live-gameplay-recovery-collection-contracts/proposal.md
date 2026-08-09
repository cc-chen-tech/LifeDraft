## Why

Recent live gameplay recovery defects involved incorrectly recognized people, missed current-event context, and opening-story drift. The existing deterministic regression contracts cover these behaviors with real domain logic and a small handwritten AI-client fake, but are not part of the maintained backend gate.

## What Changes

- Promote the existing live gameplay recovery and collection-recognition contract file into both maintained backend workflow selections.
- Keep regressions for relationship metadata gating, current-event recognition, opening-story constraints, and HTTPS music URL normalization.

## Capabilities

### New Capabilities

- `live-gameplay-recovery-collection-gate`: Maintained backend coverage protects recovered gameplay context and collection-recognition constraints.

### Modified Capabilities

- `test-gates`: The maintained backend gate includes deterministic live-gameplay recovery regressions.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
- Maintained backend test selection and coverage measurement
