## ADDED Requirements

### Requirement: Choice effects preserve resource bounds
The maintained test suite SHALL verify that choice effect normalization applies
only the delta permitted by the current player resource bounds and reports
structured warning metadata for each clamped resource.

#### Scenario: Effects cross resource bounds
- **WHEN** a player at the lower or upper resource bound receives an effect
  that would exceed that bound
- **THEN** the applied delta MUST keep the persisted resource in range and the
  returned warning MUST describe the requested and applied deltas

### Requirement: Choice wealth transactions are idempotent
The maintained test suite SHALL verify that applying the same choice wealth
transaction again does not alter the player balance or append a duplicate
ledger entry.

#### Scenario: Replayed choice transaction
- **WHEN** a choice with a numeric wealth delta is processed twice for the
  same week and round
- **THEN** the player balance and persisted ledger MUST contain exactly one
  transaction for that choice

#### Scenario: Invalid requested wealth delta
- **WHEN** a choice supplies a non-integer wealth delta
- **THEN** the player balance MUST remain unchanged and no transaction MUST be
  created
