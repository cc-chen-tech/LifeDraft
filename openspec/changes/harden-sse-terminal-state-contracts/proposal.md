## Why

SSE subscribers must observe terminal completion, failure, timeout, and reconnect responses consistently. These paths are provider-free but are under-covered in the maintained gate.

## What Changes
- Add pure terminal-state SSE contracts and promote the existing thread-pool lifecycle contract.
- Add both suites to maintained workflows with exact path parity.

## Capabilities
### New Capabilities
- `sse-terminal-state-contracts`: Provider-free contracts for terminal SSE behavior.
### Modified Capabilities
- `test-gates`: Maintained gate covers SSE terminal state and worker-pool lifecycle.

## Impact
- Adds one test file and updates maintained workflows only.
