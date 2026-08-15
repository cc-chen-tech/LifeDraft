## ADDED Requirements

### Requirement: Pull requests have one fast pre-browser gate
The repository SHALL expose `./test.sh quick` and SHALL run it before browser installation and execution in the pull-request E2E job.

#### Scenario: Quick gate succeeds
- **WHEN** strict mypy/static checks, the maintained backend suite, strict TypeScript, and preflight Jest regressions all pass
- **THEN** `./test.sh quick` MUST return zero after executing them in that order

#### Scenario: A quick sub-gate fails
- **WHEN** any required quick sub-gate returns non-zero
- **THEN** `./test.sh quick` MUST return non-zero

#### Scenario: Pull-request E2E starts
- **WHEN** the E2E workflow runs for a pull request
- **THEN** it MUST execute `./test.sh quick` in the same job and dependency environment before installing or running Playwright

#### Scenario: Main E2E starts
- **WHEN** the E2E workflow runs for a push to main
- **THEN** it MUST skip the additional quick step

### Requirement: Complete frontend Jest and coverage have one workflow owner
`Frontend Tests` SHALL be the only workflow that executes the complete frontend Jest suite, enforces coverage, or produces the frontend coverage artifact. The PR E2E quick gate MAY execute only the explicitly bounded preflight Jest collection.

#### Scenario: Frontend coverage runs
- **WHEN** `Frontend Tests` executes
- **THEN** it MUST enforce the existing Jest thresholds, generate Cobertura and HTML reports, verify them, and upload the required artifact

#### Scenario: Coverage Report runs
- **WHEN** the coverage workflow executes
- **THEN** it MUST run and publish only maintained backend coverage

### Requirement: Deployment workflow requirements match active workflows
The production deployment gate SHALL require every active non-deployment workflow and SHALL NOT wait for deleted workflow names.

#### Scenario: Frontend Integration Tests is removed
- **WHEN** production checks one main SHA
- **THEN** its required list MUST omit `Frontend Integration Tests` and retain `Frontend Tests`, `Coverage Report`, and `E2E Tests`

### Requirement: Obsolete runs are cancelled only for pull requests
Every non-deployment workflow SHALL group pull-request runs by workflow name and pull-request number, group other runs by workflow name and commit SHA, and SHALL cancel in-progress runs only for pull requests.

#### Scenario: A pull request receives another commit
- **WHEN** the same workflow starts for the newer commit
- **THEN** the older run for that pull request MUST be eligible for cancellation

#### Scenario: Main receives another commit
- **WHEN** a later main workflow starts while an earlier main run is active
- **THEN** the earlier main run MUST NOT be cancelled
