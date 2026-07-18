## Why

The maintained backend gate exercises normal world-model updates but does not
protect invalid update rejection, empty-state behavior, or the guard that
prevents a story-introduced character from replacing a preset relationship.
Those paths encode continuity and field-safety rules that previously reached
browser-agent validation too late.

## What Changes

- Add provider-free regression tests for rejected location, career,
  commitment, and causal update payloads using a real `PlayerState`.
- Add regression tests for scheduled-event cleanup and story-character
  synchronization guard behavior.
- Register only the new test module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `world-model-update-guard-contracts`: Maintained regression coverage for
  world-model invalid-input and character-continuity guards.

### Modified Capabilities
- None.

## Impact

Affected areas are `src/game/world_model_updater.py`, the maintained workflow
test lists, and a new provider-free test module. No production behavior,
external provider, or existing test is changed.
