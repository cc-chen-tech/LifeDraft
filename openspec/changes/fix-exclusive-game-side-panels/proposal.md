# Fix Exclusive Game Side Panels

The deep UX report observed that opening collection and history controls could leave two panel/dialog surfaces visible at the same time. The play page mixed local collection state with history state from `usePlayGame`; button handlers attempted to close the other panel, but the render path still allowed both booleans to be true during state races or externally restored history state.

## Changes

- Add a local active-side-panel coordinator in `PlayPage`.
- Render collection and history side panels as mutually exclusive even if their underlying state sources temporarily disagree.
- Add a focused PlayPage regression test that reproduces the overlapping history + collection state.

## Non-Goals

- No redesign of collection or history panel content.
- No change to history selection behavior.
- No change to the unified sound console.
