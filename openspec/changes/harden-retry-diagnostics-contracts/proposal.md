## Why

Retry decisions and diagnostic evidence control whether invalid generated text is corrected or silently accepted. The stable retry suite is outside the maintained gate, and diagnostics lacks a focused no-double contract.

## What Changes

- Promote stable retry controller contracts into maintained workflows.
- Add deterministic diagnostics contracts for evidence and generated reports.

## Capabilities

### New Capabilities
- `retry-diagnostics-contract-coverage`: Maintained deterministic retry and diagnostic coverage.

### Modified Capabilities
- `test-gates`: Both maintained workflow selections include verified retry and diagnostic suites in order.

## Impact

- Test-only files, workflows, and OpenSpec artifacts.
