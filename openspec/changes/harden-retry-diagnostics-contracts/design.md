## Context

Retry and diagnostics are pure local control-plane components. Existing retry tests use hand-rolled state; new diagnostics tests can use actual result dataclasses.

## Goals / Non-Goals

**Goals:** exercise retry and diagnostic public behavior without doubles and maintain workflow parity.

**Non-Goals:** modify production control flow, existing tests, providers, databases, or browser tests.

## Decisions

- Promote the verified retry suite; add a focused diagnostics suite.
- Ratchet coverage only after two expanded maintained runs.

## Risks / Trade-offs

- [Text evidence is heuristic] -> assert explicit structured fields using unambiguous text.
