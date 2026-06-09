## Implementation

- [x] Add a regression test for one unified sound panel containing peer music and narration sections.
- [x] Update the expanded global sound panel layout to group music and narration under one surface.
- [x] Simplify embedded story narration presentation so it no longer renders as an independent bordered block.
- [x] Remove the redundant collapsed narration button so the closed sound bar is not overloaded.
- [x] Keep manual narration available inside the expanded sound panel.
- [x] Remove the redundant stop action while generated narration audio is merely ready to play.
- [x] Add regression coverage for a card-based sound mixer instead of a `divide-y` stacked toolbar.
- [x] Group embedded narration primary controls separately from voice settings and auto-read.
- [x] Simplify the collapsed sound bar to one primary sound control plus expand, with narration controls only inside the unified panel.
- [x] Add PlayPage coverage proving the story body no longer renders a standalone narration bar.
- [x] Run focused component tests for the global sound panel and story voice controls.
