## ADDED Requirements

### Requirement: Resumed stories honor preset cast authority

When the game resumes a current-round story from persisted state, the system SHALL validate that story before generating options for it.

#### Scenario: Persisted current-round story drifted away from preset people
- **Given** character settings define preset key people
- **And** the current round has a persisted story that ignores those key people and introduces a replacement relationship network
- **When** gameplay attempts to resume by generating options only
- **Then** the system SHALL reject the persisted story for options-only resume
- **And** it SHALL continue through normal round generation so the replacement relationship network is not preserved.
