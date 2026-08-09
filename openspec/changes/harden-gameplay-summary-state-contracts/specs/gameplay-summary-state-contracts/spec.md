## ADDED Requirements

### Requirement: Gameplay state response contract coverage
The maintained backend suite SHALL verify that an active in-memory game session exposes progress, current event, and narrative-style fields without overwriting the active event from stale history.

#### Scenario: Read a state with an active event
- **WHEN** a session contains player progress, an active event, and a configured narrative style
- **THEN** the state response preserves those values in its public fields

### Requirement: Deterministic summary history contract coverage
The maintained backend suite SHALL verify summary responses for empty history and bounded recent-week history without an AI provider.

#### Scenario: Summarize a bounded history after completion failure
- **WHEN** round history spans more weeks than requested and local completion fails
- **THEN** the response uses only the most recent requested weeks and returns a grounded fallback summary

#### Scenario: Summarize an empty history
- **WHEN** the active player has no usable round or decision history
- **THEN** the response returns the documented just-started summary with the correct end week
