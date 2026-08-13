## Context

Story voice output has a small provider boundary that determines metadata,
playback mode, deterministic local audio, and safe generated-file access. These
behaviors can fail before a browser renders audio, yet the maintained suite does
not currently make them release-gating contracts.

## Goals / Non-Goals

**Goals:**

- Exercise provider behavior without network access, database state, environment
  mutation, or repository-generated audio files.
- Cover stable browser fallback, deterministic synthesis, WAV structure, token
  normalization, provider selection, and path-escape refusal.
- Keep both maintained workflow lists identical.

**Non-Goals:**

- Test external OpenAI or MiniMax transport.
- Change production TTS behavior, configuration, or API routes.
- Replace browser-level playback validation.

## Decisions

- Test provider classes and pure helpers directly. This fixes contracts at the
  lowest reliable layer without introducing an HTTP fixture or a browser.
- Use explicit constructor arguments and direct instance state for the
  unavailable-provider scenario. This avoids mutable process environment state,
  which is a source of parallel test interference.
- Inspect WAV metadata with the standard-library `wave` reader instead of
  comparing raw bytes. The container format is the externally meaningful
  contract while byte-level synthesis internals may change.

## Risks / Trade-offs

- [External provider requests remain untested here] -> Existing protocol-parser
  contracts cover MiniMax parsing; real remote integrations remain outside the
  maintained gate by design.
- [Direct helper tests can miss route wiring] -> Route and browser regression
  coverage remains in its own integration and experience layers.
