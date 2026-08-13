## ADDED Requirements

### Requirement: Maintained ImageService data-helper coverage
The maintained backend workflows SHALL execute deterministic contracts for
ImageService input normalization and persisted-week selection.

#### Scenario: Character data is normalized
- **WHEN** settings use structured or legacy age, gender, and era fields
- **THEN** description and character information preserve their normalized
  semantic values.

#### Scenario: Latest saved state wins
- **WHEN** a game has a saved state with a week value
- **THEN** ImageService uses that value before falling back to initial state.
