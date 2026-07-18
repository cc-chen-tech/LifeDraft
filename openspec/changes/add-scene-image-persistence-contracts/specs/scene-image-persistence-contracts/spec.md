## ADDED Requirements

### Requirement: Valid persisted scene images are reused
The maintained backend suite SHALL verify that a scene record with an existing local file is returned without analyzing or generating a new image.

#### Scenario: Existing scene file
- **WHEN** a scene matches game, week, round, and stage and its local asset exists
- **THEN** the service SHALL return that persisted scene.

### Requirement: Appearance anchors survive image persistence
The maintained backend suite SHALL verify that an appearance anchor stored in image metadata is recovered and included in the player manifest.

#### Scenario: Stored character anchor
- **WHEN** a character image has valid appearance-anchor metadata
- **THEN** the scene service SHALL recover the anchor and use its prompt segment for the player entry.

### Requirement: Maintained workflows run scene persistence contracts
Both maintained backend workflow lists SHALL include the scene persistence contract path in matching order.

#### Scenario: Workflow parity
- **WHEN** workflow test lists are compared
- **THEN** the scene persistence contract path SHALL occur in both lists at the same position.
