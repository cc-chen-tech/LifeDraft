## Context

Provider helpers are maintained, but provider-level branches for no credential, deterministic local audio, and cached output are not. These paths accept an explicit `MiniMaxConfig` and temporary directory, so they require no environment mutation or network boundary.

## Goals / Non-Goals

**Goals:** Verify fallback metadata, local WAV output/cache reuse, payload shape, and oversized-text fallback.

**Non-Goals:** Exercise HTTP or WebSocket transport, external credentials, or retry timing.

## Decisions

- Construct `MiniMaxConfig` with explicit mapping values and temporary asset directories.
- Invoke `MiniMaxTTSProvider` with its real local-audio client, which writes deterministic WAV bytes.
- Assert public `GeneratedSpeech` metadata and artifact behavior rather than transport internals.

## Risks / Trade-offs

- [Local audio differs from provider MP3] -> It intentionally validates the provider's documented deterministic fallback path.
