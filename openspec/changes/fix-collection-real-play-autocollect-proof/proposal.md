# Change: Prove real play-page collection auto-recognition

## Why

The deep UX report found a user-visible failure mode where the story contained clear people and objects, but the collection panel still showed zero collected entities. Later fixes added auto-recognition and component-level coverage, but the browser path through the real `/play` page and top-level `收集` button was not explicitly covered.

## What Changes

- Add focused Playwright coverage for the real `/play` page.
- Verify that clicking the visible `收集` button performs initial collection load, recognition, add-entities, and refresh.
- Verify that the recognized story character becomes visible in the collection dialog with an updated count.

## Impact

- Test-only change.
- No runtime behavior change.
- Makes regressions in the real game-page collection entrypoint fail before release.
