## Why

MiniMax narration must degrade safely when credentials are unavailable and remain deterministic in local-audio mode. The maintained gate currently covers protocol parsers but not the provider-level fallback and asset lifecycle.

## What Changes

- Add provider-free MiniMax TTS fallback, local-audio, cache, and payload contracts.
- Register the new module in both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `minimax-tts-fallback-contracts`: Stable fallback and local-audio contracts for the MiniMax narration provider.

### Modified Capabilities

- None.

## Impact

- Adds one test module for `src/services/minimax_story_tts_provider.py` and matching workflow entries.
