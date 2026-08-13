## ADDED Requirements

### Requirement: Default browser stages do not overlap
The default browser gate SHALL run the complete core Playwright project once
and MUST NOT separately rerun a spec already included in that project.

#### Scenario: Core execution
- **WHEN** the browser gate starts
- **THEN** all non-AI, non-manual specs run through one core project command

#### Scenario: Selected AI regression execution
- **WHEN** the browser gate runs selected high-risk browser regressions
- **THEN** each selected command targets only the AI-heavy project

### Requirement: Frontend coverage measures production sources
The frontend coverage collector MUST exclude test source directories while
retaining production TypeScript and TSX files in scope.

#### Scenario: Test helper source
- **WHEN** a helper lives beneath a frontend test directory
- **THEN** it does not contribute uncovered production statements
