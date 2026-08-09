## ADDED Requirements

### Requirement: Explicit initial wealth is normalized deterministically
The maintained backend suite SHALL verify that generated numeric wealth values
are coerced, bounded, and selected by the documented settings-key order while
qualitative or malformed values remain unset.

#### Scenario: Formatted and bounded wealth values
- **WHEN** a settings payload supplies formatted currency, ten-thousand units,
  decimals, negative values, or values above the supported maximum
- **THEN** the initializer extracts the matching non-negative bounded integer.

#### Scenario: No explicit numeric wealth exists
- **WHEN** every accepted wealth field is qualitative, blank, boolean, or
  absent
- **THEN** extraction returns no explicit value and initial wealth uses the
  configured application default.

### Requirement: Relationship settings use a canonical shape
The maintained backend suite SHALL verify that supported relationship lists are
wrapped as `key_people` and malformed relationship or key-people values become
an empty canonical list while unrelated mapping fields are retained.

#### Scenario: List-shaped relationship payload
- **WHEN** relationships is a list of people
- **THEN** normalization returns a mapping containing that list as
  `key_people`.

#### Scenario: Malformed relationship payload
- **WHEN** relationships is non-mapping data or its `key_people` value is not
  a list
- **THEN** normalization returns an empty `key_people` list.

### Requirement: Required game creation inputs fail early
The maintained backend suite SHALL verify that empty settings and empty player
names are rejected before game initialization proceeds.

#### Scenario: Missing required input
- **WHEN** character settings or player name is empty
- **THEN** initialization raises the corresponding `ValueError`.

### Requirement: Maintained workflow parity includes initializer contracts
Both ordered backend workflow lists SHALL include the initializer input contract
exactly once at the same position.

#### Scenario: Workflow list comparison
- **WHEN** coverage and backend test workflow entries are parsed in order
- **THEN** they are equal and contain the initializer input contract once.
