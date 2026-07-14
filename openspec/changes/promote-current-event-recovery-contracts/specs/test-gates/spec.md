## ADDED Requirements

### Requirement: Maintained gates cover current-event recovery
The maintained backend workflows SHALL include deterministic contracts for restoring saved current events and producing fallback options after options generation exceeds its bounded timeout.

#### Scenario: Refresh during incomplete event generation
- **WHEN** a saved current event has valid, missing, or malformed options
- **THEN** the maintained backend gate MUST fail if the saved story is lost or recovery remains without options
