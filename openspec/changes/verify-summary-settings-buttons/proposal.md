# Verify Summary And Settings Buttons

## Why

The deep gameplay report flagged two control-routing regressions: summary actions could open or behave like the story assistant, and the settings button could appear to route to the wrong panel. Current `origin/main` already contains the summary routing fix, but the settings regression coverage was too weak and only asserted that some button existed.

## What Changes

- Add a focused PlayPage regression test that clicks the settings button and verifies the settings menu opens.
- Assert that clicking settings does not open the story assistant input.
- Preserve the existing ChatBar summary tests that verify collapsed and expanded summary actions open the dedicated life-summary panel.

## Impact

- Frontend regression coverage only.
- No runtime UI behavior change.
