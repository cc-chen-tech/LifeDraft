## Why

SessionStore holds in-memory gameplay state used for reconnect replay and option reuse. Maintained coverage does not directly protect cache trimming, story-sensitive option reuse, or owner-isolated lifecycle behavior.

## What Changes

- Add deterministic contracts for SSE replay, option-cache invalidation, user isolation, and expired-session cleanup.
- Add the new module to both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `session-store-replay-contracts`: Maintained contracts for in-memory gameplay session replay and isolation.

### Modified Capabilities

- None.

## Impact

- Tests and workflow-list changes only; no session or API behavior changes.
