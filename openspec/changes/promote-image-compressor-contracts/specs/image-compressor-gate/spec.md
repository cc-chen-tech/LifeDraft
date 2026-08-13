## ADDED Requirements

### Requirement: Maintained gate validates image compression
The maintained backend selection SHALL validate image resizing, format conversion, aspect preservation, quality, and invalid input handling.

#### Scenario: Invalid image bytes are compressed
- **WHEN** the compressor receives invalid or empty data
- **THEN** the maintained contract MUST require a `ValueError`
