## ADDED Requirements

### Requirement: Stalled polling generation becomes actionable
The gameplay recovery flow SHALL convert stalled SSE-to-polling generation into an actionable retry or recovery state after a bounded interval.

#### Scenario: Polling receives no progress for too long
- **WHEN** SSE generation fails and polling reports no story progress past the configured stale-progress timeout
- **THEN** the frontend SHALL stop indefinite waiting
- **AND** it SHALL show an actionable retry or recovery control while preserving any already persisted story text.
