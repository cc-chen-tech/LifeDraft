## ADDED Requirements

### Requirement: Maintained gate validates language detection from saved state
The maintained backend selection SHALL validate English detection for ASCII era descriptions and Chinese fallback for missing or non-ASCII descriptions.

#### Scenario: Saved era description is ASCII
- **WHEN** recovered character settings contain an ASCII era description
- **THEN** the maintained contract MUST require language detection to return `en`
