## Why

GameLoop's user-visible fallback events and periodic summaries have low maintained coverage despite forming the last-resort continuity path when generation fails. These outcomes are deterministic and can be protected without live AI, browser, or database dependencies.

## What Changes

- Add provider-free GameLoop tests for localized fallback events and progress state.
- Add tests for four-week, yearly, and user-requested summary context and empty-history recovery.
- Promote the new module to both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `game-loop-summary-fallback-contracts`: Maintained regression coverage for GameLoop's fallback event and summary state contracts.

### Modified Capabilities

- None.

## Impact

- Affects test coverage and the paired backend workflow test lists only.
- Does not modify gameplay behavior, application APIs, providers, or persistence.
