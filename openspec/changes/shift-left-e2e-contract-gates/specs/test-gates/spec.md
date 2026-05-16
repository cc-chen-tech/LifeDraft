## ADDED Requirements

### Requirement: Browser API route drift is caught before E2E
The test gates SHALL verify API route existence from the backend route table before browser tests run.

#### Scenario: Required API route is missing
- **WHEN** a route used by browser API-contract coverage is removed or renamed
- **THEN** a non-browser contract test MUST fail before Playwright starts

### Requirement: Deprecated endpoint resurrection is caught before E2E
The test gates SHALL verify deprecated endpoint paths remain absent from the backend route table.

#### Scenario: Deprecated route is reintroduced
- **WHEN** an old stream, image, or round-scene endpoint is registered again
- **THEN** a non-browser contract test MUST fail before Playwright starts

### Requirement: Shift-left gates are wired into test.sh
The repository SHALL run shift-left route-drift checks from `test.sh` before the E2E layer.

#### Scenario: Full gate runs
- **WHEN** `./test.sh all` is executed
- **THEN** route-drift contract checks MUST run before `run_e2e_browser`
