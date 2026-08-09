## Why

Ending summaries must remain available when narrative generation succeeds or fails. Maintained tests cover template endings but not the provider-backed summary boundary and fallback.

## What Changes

- Add deterministic success and failure contracts for ending narrative generation.
- Add the module to both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `ending-summary-recovery-contracts`: Maintained ending summary provider and fallback contracts.

### Modified Capabilities

- None.

## Impact

- Tests and workflow lists only.
