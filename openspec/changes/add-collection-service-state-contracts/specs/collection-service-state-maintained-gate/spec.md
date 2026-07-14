## ADDED Requirements

### Requirement: Collection state construction is maintained
The maintained backend workflows SHALL execute deterministic CollectionService state-construction contracts.

#### Scenario: Identity and cache regression
- **WHEN** collection identity, legacy field, or cached-image behavior regresses
- **THEN** both maintained workflows fail before release.
