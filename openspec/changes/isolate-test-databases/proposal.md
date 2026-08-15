## Why

Real-database test entry points currently inherit an ambient `DATABASE_URL` or fall back to the repository's `data/game.db`. This can mutate developer data, makes runs share state, and lets local and CI results depend on the machine that executes them.

## What Changes

- Make every backend pytest entry point in `test.sh`, Make, and pre-commit create a unique SQLite database below a controlled test-run directory, then pass the same explicit `DATABASE_URL` to database initialization and pytest.
- Make the maintained backend test runner own an isolated database lifecycle in both test and coverage modes, including initialization and cleanup.
- Remove redundant workflow database initialization that can target the repository database.
- Add static contracts and real subprocess regressions proving that repeated runs do not share state and do not change `data/game.db`.
- Preserve the existing E2E database-isolation behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-gates`: Require every real-database test entry point to use an explicit per-run database that cannot be selected from user environment, `.env`, or the repository's `data/game.db`.

## Impact

Affected areas are `test.sh`, Make and pre-commit test commands, the maintained backend runner, backend and coverage workflows, governance tests, and test documentation. Product APIs, database schema, application database configuration, E2E behavior, and business logic are unchanged.
