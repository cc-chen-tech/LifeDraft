## ADDED Requirements

### Requirement: Missing player state preserves effect input
The choice processor SHALL return an independent copy of requested effects and
no resource warnings when player state is unavailable.

#### Scenario: Normalization without player state
- **WHEN** effect normalization runs without a player state
- **THEN** it MUST return equal effects in a distinct mapping and an empty
  warning collection

### Requirement: Missing player state uses empty custom-effect context
The choice processor SHALL pass empty character settings and current state to
custom-effect generation when player state is unavailable.

#### Scenario: Custom effect generation without player state
- **WHEN** custom-choice effects are generated without a player state
- **THEN** the delegated service request MUST receive empty character settings
  and an empty current-state mapping
