## ADDED Requirements

### Requirement: Maintained backend coverage floor is sixty percent
The coverage workflow SHALL fail when the curated maintained backend suite
reports total source statements coverage below 60%.

#### Scenario: Coverage remains at the verified baseline
- **WHEN** the maintained backend suite runs against the current source tree
- **THEN** it passes the 60% coverage threshold.

#### Scenario: Coverage regresses below the floor
- **WHEN** the maintained backend suite reports statements coverage below 60%
- **THEN** the coverage workflow exits unsuccessfully.

### Requirement: Coverage floor does not reclassify legacy tests
The 60% threshold SHALL apply only to the existing curated maintained suite.

#### Scenario: Legacy suite inventory remains separate
- **WHEN** the coverage workflow is inspected
- **THEN** it retains the curated test list rather than replacing it with the
  full backend test directory.
