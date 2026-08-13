## ADDED Requirements

### Requirement: Quality metrics persist and aggregate deterministically
The maintained backend gate SHALL verify that generation runs and detailed
checks stored in an isolated SQLite database produce correct pass rates, retry
counts, and failure evidence.

#### Scenario: Failed and successful checks are recorded
- **WHEN** the metrics store receives runs with fixed detailed checks
- **THEN** its aggregate queries SHALL return the expected rates, retry
distribution, and failed check evidence

### Requirement: Metric reports communicate data availability and severity
The maintained backend gate SHALL verify that metric summaries distinguish
empty data from recorded OK, WARN, and FAIL constraint rates.

#### Scenario: Report renders recorded quality status
- **WHEN** the metrics store contains fixed successful and failed checks
- **THEN** its summary SHALL include the corresponding constraint status and
failure section
