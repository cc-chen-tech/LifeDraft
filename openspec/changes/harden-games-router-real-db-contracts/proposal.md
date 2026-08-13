## Why

The games router is a high-risk persistence boundary for save/resume and
character-creation state, but its maintained coverage is still dominated by
mocked route tests. Real database contracts can lock down user ownership and
field persistence before browser validation.

## What Changes

- Add provider-free real-database contracts for game listing, deletion,
  character-setting persistence, and narrative-style read/write behavior.
- Cover deterministic helper behavior for nested setting merge and
  pre-first-round detection.
- Register the new module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `games-router-real-db-contracts`: Maintained real-database contracts for
  persisted game-router state transitions.

### Modified Capabilities
- None.

## Impact

This change adds tests and workflow entries only. It touches no production
behavior, provider configuration, schema, or existing test.
