## Why

Collection state changes are triggered from detail dialogs and action controls,
but existing panel tests focus on initial loading and tabs. Regressions in
feedback trimming, deletion routing, batch generation, or error recovery can
therefore escape to browser-agent testing.

## What Changes

- Add component integration tests for item image regeneration feedback.
- Add tests for item deletion confirmation, landmark batch generation, and
  visible error dismissal.
- Keep store actions as deterministic fixtures while rendering the real panel
  and dialog tree.

## Capabilities

### New Capabilities
- `collection-panel-action-contracts`: UI-to-store contracts for collection
  mutation and recovery actions.

### Modified Capabilities

- None.

## Impact

Adds a Jest suite and OpenSpec artifacts only. No collection API or UI behavior
is changed.
