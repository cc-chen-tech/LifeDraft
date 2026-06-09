## Why

When a player choice ends the last round of a week, the gameplay hook moves the page
directly into the weekly `summary` phase. The completed choice continuation is still
visible, but the media handoff only treated `options` and `result` as completed
story phases. As a result, automatic story reading skipped exactly the choice
continuation that appears before the weekly summary.

## What Changes

- Treat `summary` as a completed current-story phase for voice and music handoff.
- Keep the reading context pointed at the completed choice continuation, not the
  weekly summary card.
- Fetch and display result-stage scene media during the `summary` phase as well.
- Add a regression test for automatic MiniMax reading when a choice completion
  transitions into weekly summary.

## Impact

- Frontend gameplay page media handoff.
- Frontend play hook scene-media phase handling.
- PlayPage voice/music handoff tests.
- No backend API or persistence migration is required.
