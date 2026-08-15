## ADDED Requirements

### Requirement: Aggregate coverage propagates every stage failure
The repository coverage command SHALL execute backend and frontend coverage and
MUST return a non-zero exit code when either stage fails.

#### Scenario: Backend coverage fails
- **WHEN** backend coverage exits non-zero and frontend coverage succeeds
- **THEN** `./test.sh coverage` MUST exit non-zero

#### Scenario: Frontend coverage fails
- **WHEN** frontend coverage exits non-zero and backend coverage succeeds
- **THEN** `./test.sh coverage` MUST exit non-zero

#### Scenario: Both coverage stages succeed
- **WHEN** backend and frontend coverage both exit zero
- **THEN** `./test.sh coverage` MUST exit zero

### Requirement: Maintained coverage floors reflect measured suites
The maintained backend coverage gate SHALL enforce a 34% minimum and the
frontend coverage gate SHALL retain its global 70% Jest thresholds.

#### Scenario: Maintained backend drops below the floor
- **WHEN** the maintained backend suite reports less than 34% coverage
- **THEN** the backend coverage gate MUST exit non-zero

#### Scenario: Frontend drops below its configured floor
- **WHEN** frontend coverage is below any global 70% Jest threshold
- **THEN** the frontend coverage gate MUST exit non-zero

### Requirement: Coverage evidence is repository-owned and mandatory
Coverage workflows SHALL upload generated backend XML and frontend
Cobertura/HTML reports as GitHub artifacts and MUST fail when required files are
missing.

#### Scenario: Expected artifact is absent
- **WHEN** a coverage job reaches artifact upload without its expected report
- **THEN** the job MUST fail instead of warning or reporting success

#### Scenario: Coverage reports are generated
- **WHEN** backend and frontend coverage commands succeed
- **THEN** the workflows MUST retain the generated reports as GitHub artifacts

#### Scenario: External upload is unavailable
- **WHEN** Codecov credentials or service access are unavailable
- **THEN** repository coverage gates and artifacts MUST remain fully functional

### Requirement: Coverage output claims match generated files
The local aggregate coverage command SHALL report a coverage output path only
when that file exists.

#### Scenario: HTML report is missing
- **WHEN** a coverage stage does not generate its HTML report
- **THEN** `./test.sh coverage` MUST NOT claim that report was generated
