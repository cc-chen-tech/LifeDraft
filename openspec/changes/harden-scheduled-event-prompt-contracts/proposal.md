## Why

Scheduled commitments are a persisted state-machine boundary. Before a provider is called, the generated prompt must retain the original commitment, selected cast, current timeline, and era restrictions; otherwise a later browser flow can appear to abandon a prior promise.

## What Changes

- Add provider-free scheduled-event prompt contracts for Chinese and English state payloads.
- Register the test module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `scheduled-event-prompt-contracts`: Deterministic scheduled-event prompt field contracts.

### Modified Capabilities

- None.

## Impact

- Adds one test module for `src/game/round/event_generator.py`.
