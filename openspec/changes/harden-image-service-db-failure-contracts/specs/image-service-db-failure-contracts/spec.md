## ADDED Requirements

### Requirement: Local scene generation creates a durable delivery record
The scene image service SHALL persist a generated local image with its game,
week, round, stage, prompt, and storage metadata.

#### Scenario: Local provider fake returns scene bytes
- **GIVEN** a persisted game and an empty scene-image slot
- **WHEN** scene generation receives bytes from the provider fake
- **THEN** the database contains the corresponding scene row
- **AND** its storage path resolves to an existing local image file.

### Requirement: Provider failures do not leave partial scene rows
The scene image service SHALL roll back state and expose a typed service failure
when the provider rejects scene generation.

#### Scenario: Provider reports non-retryable capacity failure
- **GIVEN** a persisted game and no scene row for a slot
- **WHEN** the provider fake raises a typed capacity error
- **THEN** the caller receives `ImageProviderServiceError` with the safe failure metadata
- **AND** no scene row is persisted for that slot.
