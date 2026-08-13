## ADDED Requirements

### Requirement: State continuity contracts are deterministic
Maintained backend contracts SHALL exercise character-state, commitment, and spatial validators via public APIs using concrete local state without mocks, skips, providers, databases, randomness, or timing dependencies.

#### Scenario: Narrative contradicts stored character state
- **WHEN** story text gives a dead, severely injured, or imprisoned character an incompatible action
- **THEN** the character-state validator MUST return a failed result with the corresponding structured violation

#### Scenario: Narrative omits or breaches a commitment
- **WHEN** a critical commitment is overdue without acknowledgement or story text contradicts a pending commitment
- **THEN** the commitment validator MUST return a failed result identifying the commitment issue

#### Scenario: Narrative crosses an infeasible distance
- **WHEN** a character moves across a remote location in one round without fast travel
- **THEN** the spatial validator MUST return a failed result identifying the movement issue

#### Scenario: Fast travel justifies remote movement
- **WHEN** the same remote movement is described with a fast-travel keyword
- **THEN** the spatial validator MUST return a passing result
