## Why

During result or summary phases the page could fall back to the previous event
illustration while the result illustration was still being fetched or generated.
That made the visual scene look one step behind the story.

## What Changes

- Add a small scene-image display policy for current gameplay rendering.
- Show a result-scene loading state while a result illustration is pending.
- Only fall back to the event illustration when result loading is no longer in
  progress and no result illustration exists.

## Impact

- Frontend gameplay scene illustration rendering only.
- No API or storage changes.
