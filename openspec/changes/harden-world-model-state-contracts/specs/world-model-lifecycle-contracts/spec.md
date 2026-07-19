## ADDED Requirements

### Requirement: Causal chains retain their lifecycle state across saved player state
The world model MUST persist an active causal chain's resolution metadata through player-state serialization and MUST remove a resolved chain once it reaches the twenty-week retention boundary.

#### Scenario: Resolved causal chain is retained before the boundary
- **WHEN** a causal chain is resolved nineteen weeks earlier and the updater processes a later update
- **THEN** the chain remains with its resolution metadata in serialized player state

#### Scenario: Resolved causal chain expires at the boundary
- **WHEN** a causal chain was resolved twenty weeks earlier and the updater processes a later update
- **THEN** the chain is removed from the active world model

### Requirement: Commitment cleanup preserves unresolved work
The world model MUST remove resolved commitments at the ten-week retention boundary while retaining pending commitments.

#### Scenario: Mixed commitment lifecycle cleanup
- **WHEN** the updater processes commitments with one resolved entry at the retention boundary and one pending entry
- **THEN** only the resolved entry is removed
