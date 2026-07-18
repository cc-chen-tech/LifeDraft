## Why

Audio playback failures are exercised only by a hand-rolled stall simulation, not
through the rendered `MusicPlayer` component. Browser audio events and autoplay
rejections can therefore regress without a focused component-level contract.

## What Changes

- Add component regression tests for an audio-element error advancing to the
  next available recommendation and reporting the skipped item.
- Add a regression test that an autoplay rejection clears the switching state
  without presenting a false service outage.

## Capabilities

### New Capabilities
- `music-player-recovery-contracts`: Rendered playback recovery behavior for
  browser-originated audio failures and autoplay rejections.

### Modified Capabilities
- None.

## Impact

- New frontend test coverage under `frontend/src/__tests__/components/game/`.
- No production behavior, API contract, or existing test changes.
