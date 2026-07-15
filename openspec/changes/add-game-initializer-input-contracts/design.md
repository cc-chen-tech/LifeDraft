## Context

`GameInitializer` translates generated character settings into the initial
game-state shape. Its value coercion and relationship normalization run before
database persistence, but current maintained coverage does not exercise their
boundary inputs without mocks.

## Goals / Non-Goals

**Goals:**
- Verify numeric, formatted, bounded, and invalid wealth input behavior.
- Verify relationship payload normalization for supported and malformed shapes.
- Verify required creation inputs fail before any persistence path.

**Non-Goals:**
- Do not exercise random temporary IDs, database writes, style matching, or
  game-loop loading.
- Do not modify production parsing or defaults.

## Decisions

- Test coercion through both the helper and public settings extraction to
  capture parsing semantics and field precedence separately.
- Use an initializer without a database only for private normalization and
  precondition checks, so no persistence or external state is required.
- Keep tests table-free and deterministic; qualitative wealth labels are
  asserted as absent rather than guessed into numeric values.
- Add the suite as the final shared workflow entry to preserve ordered parity.

## Risks / Trade-offs

- [Private helper coverage couples tests to internals] → Pair helper cases with
  public extraction assertions that describe the observable contract.
- [Formatting conventions evolve] → Exercise supported numeric syntax and
  documented boundaries, not arbitrary locale parsing.

## Migration Plan

The change is additive. CI begins executing the contract after merge; reverting
removes only the new test and workflow entries.

## Open Questions

None.
