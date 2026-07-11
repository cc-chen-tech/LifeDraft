## Why

Production QA found that a selected voice could appear to revert, and that regeneration cleared the old story while narration still showed as playing and both TTS and generated music began work before replacement text was complete. Current completion gates prevent new auto-read for unfinished text, but they do not cancel old playback or clear the previous music target when the story re-enters a busy phase.

## What Changes

- Keep the persisted selected voice authoritative across settings hydration and remounts.
- Centralize completed-story media targeting for narration and music.
- On regeneration/loading, immediately clear the current media target and stop stale narration.
- Only expose replacement story text to TTS and music after a completed media phase.
- Add no-mock store/component, settings contract, real DB, and browser interaction coverage through `test.sh`.

## Capabilities

### New Capabilities
- `audio-regeneration-state`: Defines stable voice settings and cancellation behavior while story text is being replaced.

### Modified Capabilities

## Impact

- Play-page completed-media effects, story voice store, and music active-story targeting.
- Voice settings hydration and persistence regressions.
- Browser-visible playback status during regeneration.
