## ADDED Requirements

### Requirement: Maintained gate validates compressed image storage
The maintained backend test selection SHALL save real large and small images through `ImageStorageService` and verify compression, readback, dimensions, and generated URLs.

#### Scenario: Large image is persisted
- **WHEN** a large PNG is saved to local image storage
- **THEN** the maintained contract MUST require a valid retrievable image with bounded dimensions and reduced stored size
