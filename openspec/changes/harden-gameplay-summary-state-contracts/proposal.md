## Why

Gameplay state and summary responses drive save/resume screens, but their maintained coverage leaves most field construction, history selection, and provider-failure fallback unexercised. These paths can be tested through an in-memory session without invoking AI services.

## What Changes

- Add provider-free contracts for state response fields and current-event serialization.
- Add deterministic summary contracts for empty history, recent-week filtering, and grounded fallback after local generator failure.
- Register the new module in both maintained backend workflow lists.

## Capabilities

### New Capabilities

- `gameplay-summary-state-contracts`: Maintained contracts for gameplay state and summary response semantics.

### Modified Capabilities

- None.

## Impact

The change adds tests around `src/api/routers/gameplay/summary.py` and updates the two maintained backend test lists. It does not alter application code, API behavior, or provider configuration.
