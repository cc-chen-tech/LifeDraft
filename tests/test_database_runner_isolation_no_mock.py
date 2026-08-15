"""Contracts and subprocess regressions for test database isolation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time

import yaml


ROOT = Path(__file__).resolve().parents[1]
ISOLATED_DATABASE_RUNNER = (
    ROOT / "scripts" / "run-with-isolated-test-database.sh"
)


def _fingerprint(path: Path) -> tuple[str, int, int] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return (
        hashlib.sha256(path.read_bytes()).hexdigest(),
        stat.st_mtime_ns,
        stat.st_size,
    )


def _run_probe(
    tmp_path: Path,
    database_root: Path,
    ambient_database: Path,
    sequence: int,
) -> dict[str, object]:
    probe = tmp_path / "database_probe.py"
    probe.write_text(
        """from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys

database_url = os.environ["DATABASE_URL"]
prefix = "sqlite:///"
if not database_url.startswith(prefix):
    raise SystemExit(f"unexpected database URL: {database_url}")
database_path = Path(database_url.removeprefix(prefix))
connection = sqlite3.connect(database_path)
try:
    initialized = connection.execute(
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type = 'table' AND name = 'games'"
    ).fetchone()[0]
    connection.execute("CREATE TABLE isolation_probe (value INTEGER NOT NULL)")
    previous_rows = connection.execute(
        "SELECT COUNT(*) FROM isolation_probe"
    ).fetchone()[0]
    connection.execute(
        "INSERT INTO isolation_probe(value) VALUES (?)",
        (int(sys.argv[2]),),
    )
    connection.commit()
finally:
    connection.close()
Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "database_path": str(database_path),
            "initialized": initialized,
            "previous_rows": previous_rows,
        }
    ),
    encoding="utf-8",
)
""",
        encoding="utf-8",
    )
    result_path = tmp_path / f"probe-{sequence}.json"
    environment = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{ambient_database}",
        "PYTHONPATH": str(ROOT),
    }
    result = subprocess.run(
        [
            str(ISOLATED_DATABASE_RUNNER),
            str(database_root),
            sys.executable,
            sys.executable,
            str(probe),
            str(result_path),
            str(sequence),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result_path.read_text(encoding="utf-8"))


def test_runner_uses_fresh_database_and_preserves_ambient_target(
    tmp_path: Path,
) -> None:
    hostile_directory = tmp_path / "ambient"
    hostile_directory.mkdir()
    ambient_database = hostile_directory / "game.db"
    connection = sqlite3.connect(ambient_database)
    try:
        connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO sentinel(value) VALUES ('preserve-me')"
        )
        connection.commit()
    finally:
        connection.close()
    before = _fingerprint(ambient_database)

    database_root = tmp_path / "run" / "data"
    first = _run_probe(tmp_path, database_root, ambient_database, 1)
    second = _run_probe(tmp_path, database_root, ambient_database, 2)

    first_path = Path(str(first["database_path"]))
    second_path = Path(str(second["database_path"]))
    assert first["initialized"] == 1
    assert second["initialized"] == 1
    assert first["previous_rows"] == 0
    assert second["previous_rows"] == 0
    assert first_path != second_path
    assert first_path.is_relative_to(database_root.resolve())
    assert second_path.is_relative_to(database_root.resolve())
    assert not first_path.exists()
    assert not second_path.exists()
    assert list(database_root.iterdir()) == []
    assert _fingerprint(ambient_database) == before


def test_isolated_database_runner_preserves_failure_status_and_cleans(
    tmp_path: Path,
) -> None:
    database_root = tmp_path / "failure" / "data"
    result = subprocess.run(
        [
            str(ISOLATED_DATABASE_RUNNER),
            str(database_root),
            sys.executable,
            sys.executable,
            "-c",
            "raise SystemExit(7)",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 7
    assert list(database_root.iterdir()) == []


def _process_exists(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_for_path(path: Path) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {path}")


def test_isolated_database_runner_forwards_signals_and_cleans(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "signal_probe.py"
    probe.write_text(
        """import json
import os
from pathlib import Path
import time

Path(os.environ["PROBE_READY"]).write_text(
    json.dumps({"pid": os.getpid(), "url": os.environ["DATABASE_URL"]}),
    encoding="utf-8",
)
while True:
    time.sleep(1)
""",
        encoding="utf-8",
    )

    for signal_value, expected_status in (
        (signal.SIGINT, 130),
        (signal.SIGTERM, 143),
        (signal.SIGHUP, 129),
    ):
        database_root = tmp_path / signal_value.name / "data"
        ready_path = tmp_path / f"{signal_value.name}.json"
        environment = {
            **os.environ,
            "PROBE_READY": str(ready_path),
            "PYTHONPATH": str(ROOT),
        }
        process = subprocess.Popen(
            [
                str(ISOLATED_DATABASE_RUNNER),
                str(database_root),
                sys.executable,
                sys.executable,
                str(probe),
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_path(ready_path)
        probe_state = json.loads(ready_path.read_text(encoding="utf-8"))
        child_pid = int(probe_state["pid"])
        database_path = Path(
            str(probe_state["url"]).removeprefix("sqlite:///")
        )

        process.send_signal(signal_value)
        stdout, stderr = process.communicate(timeout=10)

        assert process.returncode == expected_status, stdout + stderr
        assert not _process_exists(child_pid)
        assert not database_path.exists()
        assert list(database_root.iterdir()) == []


def test_isolated_database_runner_manages_initialization_signals(
    tmp_path: Path,
) -> None:
    project = tmp_path / "slow-initialization"
    database_package = project / "src" / "database"
    database_package.mkdir(parents=True)
    (project / "src" / "__init__.py").write_text("", encoding="utf-8")
    (database_package / "__init__.py").write_text("", encoding="utf-8")
    (database_package / "models.py").write_text(
        """import json
import os
from pathlib import Path
import time

def init_db():
    Path(os.environ["INIT_READY"]).write_text(
        json.dumps({"pid": os.getpid(), "url": os.environ["DATABASE_URL"]}),
        encoding="utf-8",
    )
    while True:
        time.sleep(1)
""",
        encoding="utf-8",
    )
    ready_path = tmp_path / "initialization.json"
    database_root = tmp_path / "initialization-data"
    environment = {
        **os.environ,
        "INIT_READY": str(ready_path),
        "PYTHONPATH": str(project),
    }
    process = subprocess.Popen(
        [
            str(ISOLATED_DATABASE_RUNNER),
            str(database_root),
            sys.executable,
            sys.executable,
            "-c",
            "raise SystemExit('command must not start')",
        ],
        cwd=project,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_path(ready_path)
    init_state = json.loads(ready_path.read_text(encoding="utf-8"))
    init_pid = int(init_state["pid"])
    database_path = Path(
        str(init_state["url"]).removeprefix("sqlite:///")
    )

    try:
        process.send_signal(signal.SIGHUP)
        assert process.wait(timeout=10) == 129
        assert not _process_exists(init_pid)
        assert not database_path.exists()
        assert list(database_root.iterdir()) == []
    finally:
        if _process_exists(init_pid):
            os.kill(init_pid, signal.SIGTERM)


def test_isolated_database_runner_supports_overlapping_runs(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "overlap_probe.py"
    probe.write_text(
        """import json
import os
from pathlib import Path
import time

Path(os.environ["READY_PATH"]).write_text(
    json.dumps({"url": os.environ["DATABASE_URL"]}),
    encoding="utf-8",
)
release_path = Path(os.environ["RELEASE_PATH"])
while not release_path.exists():
    time.sleep(0.05)
""",
        encoding="utf-8",
    )
    database_root = tmp_path / "shared" / "data"
    release_path = tmp_path / "release"
    processes: list[tuple[subprocess.Popen[str], Path]] = []

    for sequence in (1, 2):
        ready_path = tmp_path / f"overlap-{sequence}.json"
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "READY_PATH": str(ready_path),
            "RELEASE_PATH": str(release_path),
        }
        process = subprocess.Popen(
            [
                str(ISOLATED_DATABASE_RUNNER),
                str(database_root),
                sys.executable,
                sys.executable,
                str(probe),
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        processes.append((process, ready_path))

    for _, ready_path in processes:
        _wait_for_path(ready_path)
    database_paths = [
        Path(
            str(json.loads(ready_path.read_text(encoding="utf-8"))["url"])
            .removeprefix("sqlite:///")
        )
        for _, ready_path in processes
    ]
    assert database_paths[0] != database_paths[1]
    assert all(path.exists() for path in database_paths)

    release_path.touch()
    for process, _ in processes:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stdout + stderr
    assert all(not path.exists() for path in database_paths)
    assert list(database_root.iterdir()) == []

    runner = ISOLATED_DATABASE_RUNNER.read_text(encoding="utf-8")
    assert 'rmdir "$database_root"' not in runner


def test_public_db_gate_delegates_database_to_init_and_pytest() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    db_body = script.split("run_db()", 1)[1].split("run_e2e_browser()", 1)[0]

    assert "run_pytest_with_isolated_database" in db_body
    direct_init = (
        'python -c "from src.database.models import init_db; init_db()"'
    )
    assert direct_init not in db_body


def test_every_public_pytest_uses_the_isolated_database_boundary() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    helper_path = (
        '"$PROJECT_DIR/scripts/run-with-isolated-test-database.sh"'
    )
    assert helper_path in script
    assert '"$TEST_DATA_DIR/pytest"' in script
    assert script.count("python -m pytest") == 1
    assert "pytest tests/" not in script
    for function_name in (
        "run_preflight",
        "run_mypy",
        "run_imports",
        "run_contract",
        "run_db",
        "run_unit",
        "run_integration",
        "run_api",
        "run_backend",
    ):
        function_body = script.split(f"{function_name}()", 1)[1].split(
            "\n}", 1
        )[0]
        assert "run_pytest_with_isolated_database" in function_body


def test_make_and_precommit_pytest_commands_use_isolated_databases() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    precommit = (ROOT / "scripts" / "pre-commit.sh").read_text(
        encoding="utf-8"
    )

    assert makefile.count("run-with-isolated-test-database.sh") == 3
    pytest_recipes = [
        line for line in makefile.splitlines() if "-m pytest tests/" in line
    ]
    assert len(pytest_recipes) == 3
    assert all(
        "run-with-isolated-test-database.sh" in line
        for line in pytest_recipes
    )
    assert 'run_isolated_pytest()' in precommit
    precommit_helper = precommit.split("run_isolated_pytest()", 1)[1].split(
        "\n}", 1
    )[0]
    assert precommit_helper.count('"$PYTHON3"') == 2
    assert '-m pytest "$@"' in precommit_helper
    assert "COVERAGE_OUTPUT=$(run_isolated_pytest" in precommit
    assert "if run_isolated_pytest tests/" in precommit


def test_maintained_modes_delegate_to_isolated_database_runner() -> None:
    runner = (ROOT / "scripts" / "run-maintained-backend-tests.sh").read_text(
        encoding="utf-8"
    )

    assert 'isolated_database_root="${TEST_RUN_DIR:-' in runner
    assert 'run-with-isolated-test-database.sh"' in runner
    assert '"${pytest_command[@]}"' in runner
    direct_init = (
        "python -c \"from src.database.models import init_db; init_db()\""
    )
    assert direct_init not in runner


def test_backend_workflows_do_not_initialize_an_ambient_database() -> None:
    for workflow_path in (
        ROOT / ".github" / "workflows" / "backend-tests.yml",
        ROOT / ".github" / "workflows" / "coverage.yml",
    ):
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        jobs = workflow["jobs"]
        assert isinstance(jobs, dict)
        for job in jobs.values():
            assert isinstance(job, dict)
            steps = job["steps"]
            assert isinstance(steps, list)
            assert all(
                step.get("name") != "Setup test database" for step in steps
            )
            assert all(
                "init_db" not in str(step.get("run", ""))
                for step in steps
            )


def test_e2e_database_isolation_contract_is_unchanged() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    e2e_body = script.split("run_e2e_browser_impl()", 1)[1].split(
        "run_unit()", 1
    )[0]

    assert 'E2E_DB_PATH="$TEST_DATA_DIR/story2_e2e.sqlite"' in script
    assert 'LOCAL_E2E_DB_URL="sqlite:///$E2E_DB_PATH"' in e2e_body
    assert e2e_body.count('DATABASE_URL="$LOCAL_E2E_DB_URL"') >= 2
