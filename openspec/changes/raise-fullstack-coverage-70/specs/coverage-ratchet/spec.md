## ADDED Requirements

### Requirement: Coverage metrics remain layer-specific
The repository SHALL report frontend Jest coverage and backend Python coverage
as separate metrics, including their respective denominators and the full
backend `src` result when maintained backend coverage runs.

#### Scenario: Coverage results are reviewed
- **WHEN** a coverage batch completes
- **THEN** its report SHALL identify whether the result represents frontend
  Jest, maintained backend tests, or the full backend suite

### Requirement: Frontend global coverage has a 70 percent floor
The frontend Jest configuration SHALL require at least 70 percent global
coverage for lines, statements, functions, and branches.

#### Scenario: Frontend coverage regresses below the floor
- **WHEN** any global frontend coverage measure is below 70 percent
- **THEN** the Jest coverage command MUST fail

### Requirement: Backend ratchets require repeated evidence
The maintained backend coverage floor SHALL increase only after two runs of
the complete maintained selection meet the proposed integer threshold while
measuring `--cov=src`.

#### Scenario: A proposed backend floor is not reproduced
- **WHEN** either of two maintained measurements is below the proposed floor
- **THEN** the backend floor MUST remain unchanged

#### Scenario: A proposed backend floor is reproduced
- **WHEN** two maintained measurements both meet the proposed floor
- **THEN** the backend coverage configuration MAY enforce that floor
