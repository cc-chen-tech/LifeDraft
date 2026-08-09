## ADDED Requirements

### Requirement: Provider-Bound Image Work Does Not Block Async API Traffic
The image API SHALL execute synchronous provider-bound image generation and regeneration work outside the asyncio event loop while preserving existing ownership checks, response schemas, and public error mapping.

#### Scenario: Unrelated API request arrives during slow image generation
- **WHEN** an image provider call remains in progress for forty seconds
- **THEN** unrelated health and character-setting requests SHALL remain serviceable without waiting for that provider call to finish

#### Scenario: Image provider fails in a worker thread
- **WHEN** an offloaded image provider call raises a typed provider or content error
- **THEN** the image route SHALL return the same public status code and safe error body used before offloading

### Requirement: Batch Image Rate-Limit Waits Remain Non-Blocking
The batch-character image route SHALL keep rate-limit delays and provider waits from blocking the asyncio event loop.

#### Scenario: Batch generation pauses between characters
- **WHEN** the route waits between two character image requests
- **THEN** unrelated async API requests SHALL continue to be processed
