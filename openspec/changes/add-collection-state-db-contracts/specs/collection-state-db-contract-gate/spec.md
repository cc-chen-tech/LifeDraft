## ADDED Requirements

### Requirement: Maintained collection state and database consistency coverage
The maintained backend workflows SHALL execute deterministic collection tests
that use a real isolated database session.

#### Scenario: URL-decoded item deletion removes state and image row
- **WHEN** an encoded item name is deleted
- **THEN** the matching PlayerState item and linked persisted image record are
  both absent after the operation.

#### Scenario: URL-decoded landmark deletion removes state and image row
- **WHEN** an encoded landmark name is deleted
- **THEN** the matching PlayerState landmark and linked persisted image record
  are both absent after the operation.

#### Scenario: Character regeneration permission remains enforced
- **WHEN** a non-player character has affinity below the required threshold
- **THEN** validation rejects image regeneration without contacting a provider.
