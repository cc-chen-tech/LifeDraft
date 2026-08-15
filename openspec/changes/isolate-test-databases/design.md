## Context

`config.settings` reads `.env` at import time and `src.database.models` creates its engine at module import time. Therefore a test runner must set `DATABASE_URL` before starting the Python process; changing the variable after importing application modules is too late. Today `./test.sh db` and the maintained backend runner do not do that, while two CI workflows separately initialize whichever database ambient configuration selects.

The change spans the public test CLI, a shared backend runner, workflows, and governance tests. It must preserve the E2E runner's existing explicit database and must not alter application database behavior.

## Goals / Non-Goals

**Goals:**

- Give each DB-backed invocation a newly created SQLite database below a controlled test-run directory.
- Ensure initialization and pytest inherit exactly the same explicit `DATABASE_URL`.
- Clean isolated database files after the command finishes, including failure paths.
- Prove isolation through static contracts and real child-process execution.
- Remove CI initialization that runs outside the isolated runner.

**Non-Goals:**

- Changing application configuration, schema, migrations, or repository code paths.
- Changing the already-isolated E2E database lifecycle.
- Reclassifying pytest markers, adding parallelism, or expanding coverage targets.

## Decisions

### Use one shared shell boundary for database lifecycle

A new shell helper will create a unique directory with `mktemp`, export a SQLite `DATABASE_URL`, initialize the schema, execute the supplied command, and remove the directory through an exit trap. Every backend pytest invocation in `test.sh`, including `test.sh db`, and the maintained backend runner will call this helper.

Centralizing the boundary avoids two implementations drifting. Passing an environment variable directly to separate commands was considered, but it would duplicate cleanup and make it easier for initialization and pytest to use different values.

### Set `DATABASE_URL` before every Python child starts

The helper exports the URL before importing `src.database.models`. This takes precedence over an inherited variable and over `.env`, which is necessary because settings and the SQLAlchemy engine are initialized during import. Callers also provide the Python interpreter so schema initialization and pytest cannot accidentally use different environments.

Changing `config.settings` for tests was rejected because it would change product configuration behavior and still depend on import order.

### Place databases below explicit run roots

`test.sh` passes a root below `$TEST_RUN_DIR/data/` for every pytest process. The maintained runner uses `$TEST_RUN_DIR/data/` when supplied by an aggregate command and otherwise creates a private root below `$TEST_RUN_ROOT` or the system temporary directory. Each invocation gets a distinct child directory, so two runs cannot share state.

### Let maintained runners initialize their own database

Backend and coverage workflows will call only the maintained runner. Their standalone setup steps will be removed because they initialize a database that the actual tests must neither rely on nor target.

### Forward termination to the isolated command process group

The helper launches the requested command in a separate POSIX session, records its process-group leader, and forwards INT, TERM, or HUP before waiting for it. The wrapper then returns the command's normal status or the conventional signal status and performs idempotent cleanup.

## Risks / Trade-offs

- [A killed process could bypass normal shell cleanup] → Keep databases under temporary test-run roots, forward signals to the isolated child process group, wait for it, and perform idempotent exit cleanup; later runs never reuse old directories.
- [SQLite URL construction can be sensitive to relative paths] → Resolve the database root to an absolute path before exporting the URL.
- [Tests that cache imported database modules could retain another engine] → Isolation occurs outside pytest, before its Python interpreter starts.
- [The added initialization has a small runtime cost] → It replaces redundant CI initialization and prioritizes deterministic safety over a small setup cost.

## Migration Plan

Land the helper, both runner integrations, workflow removals, and regressions together. Rollback is a single code revert; no persistent data or schema migration is involved because isolated files are temporary.

## Open Questions

None.
