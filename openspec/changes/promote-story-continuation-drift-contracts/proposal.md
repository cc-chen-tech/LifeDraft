## Why

Story continuation drift can introduce invented cast, genre contamination, and
anachronistic chapter titles. A provider-free regression suite verifies quick
validation and rewrite retries but is not in the maintained gate.

## What Changes

- Promote verified continuation and rewrite drift contracts to both maintained
  backend workflows.
- Keep coverage-floor increases dependent on complete-run evidence.

## Capabilities

### New Capabilities
- `story-continuation-drift-gate`: Maintained coverage of timeline and cast
  drift detection plus retry behavior.

### Modified Capabilities
- `test-gates`: Both maintained workflows include continuation drift contracts.

## Impact

- Affected source under test: `src/game/story_service.py` and story rewrite
  validation paths.
- No production behavior or existing test content changes.
