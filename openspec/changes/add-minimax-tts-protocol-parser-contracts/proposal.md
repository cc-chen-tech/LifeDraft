## Why

MiniMax TTS protocol parsing controls whether generated narration is usable,
but several response-shape and archive-safety branches are absent from the
maintained backend gate.

## What Changes

- Add provider-free tests for TTS protocol helpers and audio archive handling.
- Register the new module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `minimax-tts-protocol-parser-contracts`: Maintained contracts for MiniMax
  TTS response parsing, audio extraction, and URL safety.

### Modified Capabilities

- None.

## Impact

Tests and workflow lists only; no production or external network changes.
