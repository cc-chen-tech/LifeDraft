## Context

The collection router derives recognition history and character eligibility from `PlayerState`. The existing contract uses only `SimpleNamespace` state and validates current unresolved events, relationship effects, storylines, and habits.

## Goals / Non-Goals

**Goals:** Promote this deterministic router contract in both maintained workflows and preserve ordered selection parity.

**Non-Goals:** Change collection behavior, call external services, or add mocks, skips, random input, or environment mutation.

## Decisions

- Promote the existing two-test contract because it directly executes the collection-router derivation helpers.
- Append it to both selections and retain the current threshold unless the complete suite proves the next threshold.

## Risks / Trade-offs

- [Helper-level coverage does not prove HTTP authorization] -> Keep API endpoint coverage in separate integration tests.
