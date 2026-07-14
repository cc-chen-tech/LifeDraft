## ADDED Requirements

### Requirement: Maintained gate protects gameplay event protocol safeguards
The maintained backend selection SHALL verify per-user/global SSE capacity, safe release, terminal resume-view blocking, and valid reconnect cursor parsing.

#### Scenario: Reconnect has an invalid cursor
- **WHEN** a gameplay request supplies a non-numeric `Last-Event-ID`
- **THEN** the maintained contract MUST require a 400 validation error

#### Scenario: Saved terminal view awaits acknowledgement
- **WHEN** a recovered game has a result, summary, or ending resume view
- **THEN** the maintained contract MUST require new event generation to be blocked
