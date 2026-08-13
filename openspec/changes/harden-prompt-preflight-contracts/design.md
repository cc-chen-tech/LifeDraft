## Context

`PreflightChecker` is a pure local prompt boundary. Existing tests cover critical context emptiness but do not establish the full marker, token, or optional-context contract.

## Goals / Non-Goals

**Goals:** cover deterministic public results without providers, mocks, databases, randomness, or timing; preserve workflow parity.

**Non-Goals:** change marker policy, token thresholds, production code, or existing tests.

## Decisions

- Use real prompt strings and a real empty registry because checker behavior is registry-independent.
- Promote only after two focused runs and ratchet coverage only after two complete runs.

## Risks / Trade-offs

- [Threshold coupling] -> Assert stable named marker and numeric boundary behavior rather than log output.
