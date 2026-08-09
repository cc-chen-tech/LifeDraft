## Context

`process_decision` coordinates resource mutation, the authoritative wealth
ledger, character relationships, and audit history. It can execute without an
AI generator when result generation is disabled.

## Goals / Non-Goals

**Goals:** Verify state invariants with concrete `PlayerState` objects.

**Non-Goals:** Invoke AI result generation, add mocks, or alter choice logic.

## Decisions

- Test result generation disabled, so all assertions are deterministic.
- Assert ledger transaction identity and resulting state rather than internals.

## Risks / Trade-offs

- [Choice effects may evolve] -> Keep assertions on persisted state contracts.
