## ADDED Requirements

### Requirement: Maintained gates cover pure image-provider contracts
The maintained backend test and coverage workflows SHALL include provider-free image-generator contracts for request normalization and safe response classification.

#### Scenario: Image provider protocol regression
- **WHEN** a change breaks deterministic request normalization or typed response classification
- **THEN** the maintained backend gate MUST fail before release-only provider validation
