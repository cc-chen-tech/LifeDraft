## ADDED Requirements

### Requirement: Collection refresh preserves visible data
The system SHALL keep existing collection data visible while refreshing generated images, descriptions, and recognized entities.

#### Scenario: Refresh during image generation
- **WHEN** a collection refresh occurs while an entity image is being generated
- **THEN** existing list items and available image URLs MUST remain visible until replacement data is available

#### Scenario: Refresh after generated image completes
- **WHEN** backend returns a generated image URL for an entity
- **THEN** the collection UI MUST update that entity without clearing unrelated entities

### Requirement: Collection detail selection survives refresh
The system SHALL preserve the selected character, item, or landmark detail after refresh when the entity still exists.

#### Scenario: Selected entity still exists
- **WHEN** the selected entity is present in refreshed collection data
- **THEN** the detail panel MUST remain open with refreshed fields for that entity

#### Scenario: Selected entity deleted
- **WHEN** the selected entity is absent from refreshed collection data
- **THEN** the detail panel MUST close or return to the list state

### Requirement: Collection loading states distinguish initial load from refresh
The system SHALL distinguish initial loading from background refreshing.

#### Scenario: Initial open
- **WHEN** the collection panel is opened with no loaded data
- **THEN** the UI MAY show a loading state

#### Scenario: Background refresh
- **WHEN** collection data already exists and a refresh begins
- **THEN** the UI MUST keep existing data visible and use non-blocking refresh indicators
