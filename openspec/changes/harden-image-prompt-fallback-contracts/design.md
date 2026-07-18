## Context

The prompt builder has provider-facing paths and a deterministic fallback layer. The fallback layer determines how a user sees a scene when provider configuration or generation is unavailable, so it must be verified independently of API transport.

## Goals / Non-Goals

**Goals:** Verify sanitization, prompt defaults, bounded fallback scene text, and structured visual-anchor extraction.

**Non-Goals:** Invoke OpenAI-compatible clients, change prompt wording, or assert provider payloads.

## Decisions

- Exercise public and private deterministic helpers directly with fixed input text.
- Assert semantic invariants rather than the entire large prompt, keeping tests stable when unrelated wording evolves.
- Keep provider transport behavior in its existing provider contract tests.

## Risks / Trade-offs

- [Prompt text evolves] -> Assertions focus on mandatory safety and identity segments.
- [Fallback does not validate provider responses] -> That boundary remains covered by separate transport tests.
