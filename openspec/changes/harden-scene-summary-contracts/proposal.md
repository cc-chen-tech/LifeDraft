## Why

The maintained backend gate still leaves scene-character formatting and
historical-summary relevance selection below the coverage expected for gameplay
state contracts. Both are deterministic helpers whose regressions should be
caught before a browser, provider, or asynchronous stream is involved.

## What Changes

- Add deterministic `PlayerState` contracts for historical-summary keyword
  collection, relevance scoring, and future-summary exclusion.
- Promote the existing, provider-free multi-character scene contract suite only
  after repeatable local verification.
- Keep both maintained backend workflow selections identical and raise the
  integer coverage floor only when two measured runs support it.

## Capabilities

### New Capabilities
- `scene-summary-contract-coverage`: Stable state and formatting contracts for
  scene-character manifests and historical-summary selection.

### Modified Capabilities
- `test-gates`: Maintained backend workflows include only twice-verified,
  deterministic scene and summary contract suites in matching order.

## Impact

- Adds tests for `src/game/historical_summary_selector.py`.
- Includes an existing pure contract suite for
  `src/services/image/scene_service.py` in maintained workflows.
- Does not modify production code or existing tests.
