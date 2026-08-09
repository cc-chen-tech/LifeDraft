## Context

Music provider payload parsing is a pure boundary with low maintained coverage.
It can be tested with fixed response dictionaries without network state.

## Goals / Non-Goals

**Goals:** Cover URL, bytes, duration, provider-error, and summary parsing.

**Non-Goals:** Change generation requests, providers, or external APIs.

## Decisions

- Use fixed nested payloads and assert accepted values plus invalid-value fallbacks.
- Keep tests provider-free and add them symmetrically to maintained workflows.

## Risks / Trade-offs

- [Schemas evolve] → Assert supported field families, not unrelated payload shape.
