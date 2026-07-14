## Why

Prompt preflight is the last deterministic check before constraints are sent to generation, but maintained coverage only exercises two context edge cases. Missing markers, token warnings, and optional context reporting need stable local contracts.

## What Changes

- Add no-double public preflight contracts for complete prompts, missing markers, token limits, and context completeness.
- Promote the stable existing preflight context suite and new contracts symmetrically into maintained workflows.

## Capabilities

### New Capabilities
- `prompt-preflight-contract-coverage`: Deterministic maintained contracts for prompt completeness and context reporting.

### Modified Capabilities
- `test-gates`: Maintained workflow selections include verified prompt preflight contracts in identical order.

## Impact

- Test files, workflow lists, and OpenSpec artifacts only; no production or existing test changes.
