## ADDED Requirements

### Requirement: Summary response recovery is maintained
The maintained backend workflows SHALL execute local SummaryGenerator response-recovery contracts.

#### Scenario: Structured summary response regression
- **WHEN** a summary response includes valid data, formatting artifacts, absent world categories, or invalid bonus effects
- **THEN** the returned summary state preserves valid content and applies deterministic normalization and defaults.
