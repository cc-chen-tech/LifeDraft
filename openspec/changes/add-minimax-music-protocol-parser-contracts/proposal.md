## Why

MiniMax music generation accepts varied provider response shapes, and parser
regressions currently escape the maintained backend gate despite directly
affecting playable audio delivery.

## What Changes

- Add provider-free contracts for audio URL, bytes, duration, and error parsing.
- Add contracts for normalized story summaries used in music requests.
- Register the new module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `minimax-music-protocol-parser-contracts`: Maintained contracts for MiniMax
  music provider response parsing and request-boundary normalization.

### Modified Capabilities

- None.

## Impact

Adds tests and CI workflow entries only; no production provider behavior changes.
