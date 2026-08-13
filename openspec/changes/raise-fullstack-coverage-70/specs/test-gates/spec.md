## ADDED Requirements

### Requirement: Maintained workflow selections remain equivalent
The system SHALL keep the maintained test-file selections in the backend
coverage workflow and the backend test workflow in the same order.

#### Scenario: A maintained backend suite is added
- **WHEN** a stable backend suite is promoted to maintained coverage
- **THEN** both workflows MUST select that suite before the change is merged

#### Scenario: Workflow selections diverge
- **WHEN** the two maintained workflow selections differ in file membership or
  order
- **THEN** the coverage change MUST NOT be committed
