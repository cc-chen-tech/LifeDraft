## ADDED Requirements

### Requirement: MiniMax music response parsing is maintained
The maintained backend suite SHALL verify nested audio URL, encoded bytes,
duration, and provider-error response fields.

#### Scenario: Nested audio response
- **WHEN** the provider response places audio fields under `data`
- **THEN** valid audio URL, bytes, and duration are recovered

### Requirement: MiniMax music request summaries are maintained
The maintained backend suite SHALL verify story summaries are whitespace-normalized
and bounded before entering the music-generation boundary.

#### Scenario: Long multiline summary
- **WHEN** the story exceeds the configured summary limit
- **THEN** whitespace is collapsed and the result is safely truncated
