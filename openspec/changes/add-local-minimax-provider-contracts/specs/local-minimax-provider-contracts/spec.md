## ADDED Requirements

### Requirement: Maintained gate verifies MiniMax text generation transport
The maintained backend gate SHALL exercise text-to-image generation against a loopback-only MiniMax-compatible HTTP server.

#### Scenario: Text generation returns an image URL
- **WHEN** the loopback provider returns an image URL for a text-to-image request
- **THEN** the contract MUST require the generator to send the MiniMax request shape and return the downloaded image bytes

### Requirement: Maintained gate verifies MiniMax image-edit transport
The maintained backend gate SHALL exercise image-to-image generation against the loopback provider.

#### Scenario: Image edit returns multiple image URLs
- **WHEN** the loopback provider returns two edited image URLs
- **THEN** the contract MUST require the generator to submit the reference as a subject reference and return both downloaded variants

### Requirement: Provider failures remain typed
The maintained backend gate SHALL verify that a provider response error becomes a typed image provider error.

#### Scenario: Provider reports exhausted capacity
- **WHEN** the loopback provider returns a non-zero MiniMax capacity status
- **THEN** the generator MUST raise a non-retryable capacity `ImageProviderError`
