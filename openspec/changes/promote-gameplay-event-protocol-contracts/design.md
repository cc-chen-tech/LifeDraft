## Context

The gameplay event router owns SSE connection accounting, recovered terminal-view gating, and reconnect cursor parsing. The existing test calls these real helpers with framework request objects and simple state containers, without provider access.

## Goals / Non-Goals

**Goals:** Promote the deterministic protocol regression file in both maintained workflows with ordered parity.

**Non-Goals:** Change router behavior, simulate a provider, or introduce mocks, skips, environment mutation, or random input.

## Decisions

- Promote the existing file because it directly covers the router safety branches that have historically surfaced in browser-agent recovery flows.
- Keep the threshold unchanged unless the complete suite passes its next strict candidate.

## Risks / Trade-offs

- [Helper coverage does not replace a full SSE transport test] -> Retain the existing SSE stream contracts and browser E2E coverage separately.
