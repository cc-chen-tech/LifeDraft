## Why

Round finalization applies player-visible weekly rewards, writes durable summaries, and advances game time. The maintained suite covers component helpers but not this ledger-backed orchestration path.

## What Changes

- Add provider-free RoundFinalizer contracts for weekly reward application and status notification.
- Add deterministic contracts for four-week and yearly summary record boundaries.
- Add the new module to both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `round-finalization-ledger-contracts`: Maintained coverage for RoundFinalizer reward, summary, and periodic-record state transitions.

### Modified Capabilities

- None.

## Impact

- Tests and maintained workflow lists only; no changes to game rules, thread scheduling, or persistence APIs.
