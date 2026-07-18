## Why

Story voice playback is browser-visible, but the maintained backend suite barely
exercises provider selection, browser fallback, deterministic audio generation,
or filename safety. Regressions in these contracts currently reach browser
validation later than necessary.

## What Changes

- Add provider-free contract tests for browser fallback and deterministic story
  TTS behavior.
- Verify deterministic WAV shape, safe token normalization, provider selection,
  and unavailable-backend fallback.
- Register the test module in both maintained backend workflows.

## Capabilities

### New Capabilities

- `story-tts-provider-contracts`: Maintained contracts for story TTS provider
  metadata, playback behavior, deterministic audio, and file access boundaries.

### Modified Capabilities

- None.

## Impact

Adds a focused test module and workflow entries only. Production story TTS
implementation, API behavior, and external provider integrations remain
unchanged.
