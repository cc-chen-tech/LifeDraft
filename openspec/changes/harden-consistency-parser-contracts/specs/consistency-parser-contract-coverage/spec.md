## ADDED Requirements

### Requirement: Consistency response parsing is deterministic
Maintained tests SHALL validate local consistency response parsing without invoking an AI client.

#### Scenario: Critical issue omits should_retry
- **WHEN** parsed JSON has a critical issue but omits should_retry
- **THEN** the result MUST fail and contain fix instructions
