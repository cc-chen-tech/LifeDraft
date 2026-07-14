## ADDED Requirements

### Requirement: Image generator normalizes MiniMax requests deterministically
The image generator SHALL construct provider payloads from supported sizes, response formats, prompt constraints, output counts, references, and caller overrides without requiring a network call.

#### Scenario: Supported payload inputs
- **WHEN** a caller supplies valid size, prompt, output-count, reference, and override inputs
- **THEN** the generated MiniMax payload MUST contain the normalized provider fields and MUST omit unsupported legacy fields

#### Scenario: Invalid or oversized prompt inputs
- **WHEN** a caller supplies an invalid size or prompt exceeding the provider limit
- **THEN** the normalized payload MUST use the safe aspect-ratio fallback and prompt-length limit

### Requirement: Image generator safely classifies provider data
The image generator SHALL classify provider errors and malformed image data into typed, safe failures without exposing provider response internals.

#### Scenario: Provider error status
- **WHEN** a MiniMax response contains a recognized capacity, authentication, or content-safety status
- **THEN** the helper MUST raise the corresponding typed exception with stable public semantics

#### Scenario: Malformed image source
- **WHEN** a provider response contains no usable source or invalid base64 payload
- **THEN** the helper MUST raise a non-retryable invalid-response error
