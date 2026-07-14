## Why

The style-aware prompt builder defines the hard and soft writing constraints
sent to story generation, yet its maintained coverage is only 11.5%. A legacy
test module cannot enter the gate because its historical TDD wording trips the
no-skip hygiene scan.

## What Changes

- Add no-mock contracts for full style rendering, optional-field omission,
  chapter guidance, temperature scheduling, and deterministic prompt budgeting.
- Promote only the new suite to both maintained backend workflows.

## Capabilities

### New Capabilities

- `style-prompt-builder-contract-gate`: Maintained coverage for the pure style
  manifest to prompt transformation boundary.

### Modified Capabilities

- None.

## Impact

- `tests/test_style_prompt_builder_contracts.py`
- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
