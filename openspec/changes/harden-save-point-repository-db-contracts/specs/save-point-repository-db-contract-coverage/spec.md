## ADDED Requirements

### Requirement: Save points preserve manual checkpoint semantics
The maintained backend suite SHALL verify with real SQLite storage that manual
save points retain their label and player identity, remain distinct from
automatic snapshots, and appear in the complete state timeline.

#### Scenario: Manual checkpoint alongside automatic snapshot
- **WHEN** a player creates a named save point for a game with an automatic snapshot
- **THEN** the save-point list MUST contain only the manual checkpoint and the
  full timeline MUST retain both records.

### Requirement: Save-point access respects game ownership
The maintained backend suite SHALL verify that only the owning user can load or
delete a save point.

#### Scenario: Foreign user attempts rewind access
- **WHEN** a different user loads or deletes a save point
- **THEN** the repository MUST deny access while the owner can load and delete it.

### Requirement: Maintained workflows run save-point repository contracts
Both maintained backend workflow lists SHALL include the save-point repository
contract path in matching order.

#### Scenario: Workflow parity
- **WHEN** the maintained workflow test lists are compared
- **THEN** the save-point contract path SHALL occur in both lists at the same position.
