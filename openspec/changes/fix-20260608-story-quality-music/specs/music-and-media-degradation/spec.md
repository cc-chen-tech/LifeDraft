## ADDED Requirements

### Requirement: Music API failures are structured JSON
Music API routes SHALL return structured JSON degradation responses for provider failures instead of gateway HTML, empty responses, or unhandled exceptions.

#### Scenario: Recommendation provider fails
- **WHEN** a music provider request fails, times out, or returns invalid data
- **THEN** `/api/music/recommend` SHALL return JSON with an empty or degraded recommendation payload
- **AND** gameplay controls SHALL remain usable.

#### Scenario: Generated music provider fails
- **WHEN** `/api/music/generate` cannot create a playable generated track
- **THEN** it SHALL return JSON describing the unavailable generated track
- **AND** it SHALL not interrupt the current NetEase queue or story flow.
