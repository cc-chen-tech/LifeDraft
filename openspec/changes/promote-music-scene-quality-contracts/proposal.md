## Why

Story-to-music matching is visible gameplay behavior: an era or negative-cue regression produces inappropriate tracks even when backend requests still succeed. Existing deterministic quality contracts exercise this logic deeply but are outside the maintained gate.

## What Changes

- Add existing music scene-quality and era-recommendation contract suites to both maintained backend workflows.
- Preserve identical ordered workflow selections.
- Raise the maintained floor only if the expanded suite proves the next integer threshold.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `test-gates`: The maintained backend gate covers story-to-music scene fit, safe candidate selection, prompt bounds, and era-aware recommendation context.

## Impact

- Affects only the two maintained workflow lists.
- Promotes existing provider-free contract tests without changing production code or test implementations.
