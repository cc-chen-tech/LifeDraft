## ADDED Requirements

### Requirement: Image router preserves owned asset fields
The maintained backend suite SHALL verify that image reads return active asset
fields and soft deletion removes an asset from subsequent game listings.

#### Scenario: Owned image is deleted
- **WHEN** an owner deletes an existing image
- **THEN** the endpoint MUST mark it inactive and exclude it from the game list.

### Requirement: Scene reads preserve week and stage identity
The maintained backend suite SHALL verify that scene reads select the requested
week and stage and that listing returns the stored scene identity fields.

#### Scenario: Same round across weeks
- **WHEN** scenes exist for the same round in different weeks
- **THEN** the requested week and stage MUST identify the returned scene.

### Requirement: Maintained workflows run image router read contracts
Both maintained backend workflow lists SHALL include the image router contract
path in matching order.

#### Scenario: Workflow parity
- **WHEN** workflow test lists are compared
- **THEN** the image router contract path SHALL occur in both lists at the same position.
