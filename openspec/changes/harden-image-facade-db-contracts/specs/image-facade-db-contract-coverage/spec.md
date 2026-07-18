## ADDED Requirements

### Requirement: Image facade selects active stored assets
The maintained backend suite SHALL verify that the image facade returns only
active assets and selects the newest active version for an entity.

#### Scenario: Active entity image lookup
- **WHEN** a game has active and inactive image versions
- **THEN** the facade MUST return the newest active version and exclude inactive rows.

### Requirement: Image facade normalizes stored character context
The maintained backend suite SHALL verify character description and era context
from supported structured and legacy setting shapes.

#### Scenario: Structured character settings
- **WHEN** age, gender, world, and era data are present in character settings
- **THEN** the facade MUST return the compact display-ready context.

### Requirement: Maintained workflows run image facade contracts
Both maintained backend workflow lists SHALL include the image facade contract
path in matching order.

#### Scenario: Workflow parity
- **WHEN** maintained workflow test lists are compared
- **THEN** the image facade contract path SHALL occur in both lists at the same position.
