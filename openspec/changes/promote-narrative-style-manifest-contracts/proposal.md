## Why

Narrative style manifests govern structured style data, local loading, and
cache behavior, but their deterministic suite is excluded from maintained
backend coverage. Its 91% direct statement coverage provides a high-value way
to detect regressions in a shared narrative configuration boundary.

## What Changes

- Add `tests/test_narrative_style_manifest.py` to the ordered selections of
  both maintained backend workflows.
- Define regression and parity requirements for the promoted suite.
- Verify direct execution, gate-dependency hygiene, workflow parity, and the
  complete coverage gate; raise the maintained threshold only if it passes.

## Capabilities

### New Capabilities
- `narrative-style-manifest-contract-gate`: Maintained coverage for style
  manifest structure, serialization, local loader behavior, cache, and
  malformed-input handling.

### Modified Capabilities

- None.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
- Existing `tests/test_narrative_style_manifest.py` is executed by maintained
  CI without modifying source or test assertions.
