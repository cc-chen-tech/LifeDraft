## Why

Entity-recognition task state, character introduction, and relationship events directly affect gameplay continuity, but their deterministic regression suites are missing from the maintained backend gate. Promoting the verified suites moves failures from late manual gameplay checks into release-time validation.

## What Changes

- Add the existing entity-recognition task lifecycle suite to both maintained backend workflows.
- Add the existing character-introduction timing and queue contracts.
- Add the existing relationship service compatibility and event-trigger contracts.
- Preserve ordered workflow parity and existing gate constraints.

## Capabilities

### New Capabilities
- `gameplay-relationship-entity-maintained-gate`: Require deterministic entity-task, character-introduction, and relationship-event contracts in the maintained backend suite.

### Modified Capabilities

- None.

## Impact

Only the two workflow test lists change. The selected tests run in-process against concrete game state and contain no provider, browser, or mock dependency.
