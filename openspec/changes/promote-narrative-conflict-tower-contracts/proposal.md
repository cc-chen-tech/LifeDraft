## Why

`ConflictTower` implements narrative conflict escalation and player-deviation
rules, but its deterministic contract tests are not part of the maintained
backend coverage gate. Promoting them provides regression protection for a
high-risk narrative state component while increasing measured maintained
coverage with tests that do not depend on providers, network, or mock
frameworks.

## What Changes

- Add the deterministic `ConflictTower` contract suite to both maintained
  backend workflow selections.
- Keep the two workflow selections in identical order so the coverage and
  backend-test jobs exercise the same maintained scope.
- Record the promotion criteria and verification requirements for this suite.

## Capabilities

### New Capabilities
- `narrative-conflict-tower-contract-gate`: Maintained regression coverage for
  conflict-tier management, escalation, storyline deviation, style, and
  degradation behavior.

### Modified Capabilities

- None.

## Impact

- `.github/workflows/coverage.yml`
- `.github/workflows/backend-tests.yml`
- `tests/test_narrative_conflict_tower.py` is executed by maintained CI without
  modifying its existing assertions.
