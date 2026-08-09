## ADDED Requirements

### Requirement: Retry and diagnostics contracts are maintained
The maintained backend gate SHALL exercise retry decisions and diagnostic evidence/report generation through local public APIs without mocks, skips, providers, databases, randomness, or timing dependencies.

#### Scenario: Critical validation failure is diagnosed
- **WHEN** a critical failed validation check identifies an unknown person
- **THEN** diagnostics MUST produce a critical report with evidence and a suggested fix

#### Scenario: No violation exists
- **WHEN** validation contains no failed checks
- **THEN** diagnostics MUST report zero violations and a passing summary
