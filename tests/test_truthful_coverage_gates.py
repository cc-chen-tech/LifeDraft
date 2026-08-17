"""Behavior and workflow contracts for truthful coverage gates."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o755)


def _run_public_coverage(
    tmp_path: Path,
    *,
    backend_status: int,
    frontend_status: int,
    reports_to_create: tuple[str, ...],
    stale_reports: tuple[str, ...] = (),
    block_backend_cleanup: bool = False,
) -> subprocess.CompletedProcess[str]:
    project = tmp_path / "project"
    project.mkdir()
    test_script = project / "test.sh"
    shutil.copy2(ROOT / "test.sh", test_script)
    test_script.chmod(0o755)

    log_path = tmp_path / "coverage-stages.log"
    _write_executable(
        project / "scripts" / "run-maintained-backend-tests.sh",
        """#!/bin/bash
printf 'backend:%s\\n' "$*" >> "$COVERAGE_FIXTURE_LOG"
if [ "$BACKEND_WRITE_REPORT" = "1" ]; then
    mkdir -p "$(dirname "$COVERAGE_XML_PATH")"
    printf 'backend coverage\\n' > "$COVERAGE_XML_PATH"
fi
exit "$BACKEND_STATUS"
""",
    )
    (project / "frontend").mkdir()
    fake_bin = tmp_path / "bin"
    _write_executable(
        fake_bin / "npm",
        """#!/bin/bash
printf 'frontend:%s\\n' "$*" >> "$COVERAGE_FIXTURE_LOG"
coverage_dir=''
for arg in "$@"; do
    case "$arg" in
        --coverageDirectory=*) coverage_dir="${arg#*=}" ;;
    esac
done
if [ "$FRONTEND_WRITE_REPORT" = "1" ]; then
    mkdir -p "$coverage_dir"
    printf 'frontend coverage\\n' > "$coverage_dir/index.html"
fi
exit "$FRONTEND_STATUS"
""",
    )

    run_directory = tmp_path / "run"
    backend_report = run_directory / "coverage.xml"
    frontend_report = run_directory / "frontend" / "coverage" / "index.html"
    reports = {"backend": backend_report, "frontend": frontend_report}
    for report_name in stale_reports:
        report = reports[report_name]
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("stale coverage", encoding="utf-8")
    if block_backend_cleanup:
        backend_report.mkdir(parents=True)

    environment = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "TEST_RUN_DIR": str(run_directory),
        "COVERAGE_FIXTURE_LOG": str(log_path),
        "BACKEND_STATUS": str(backend_status),
        "FRONTEND_STATUS": str(frontend_status),
        "BACKEND_WRITE_REPORT": (
            "1" if "backend" in reports_to_create else "0"
        ),
        "FRONTEND_WRITE_REPORT": (
            "1" if "frontend" in reports_to_create else "0"
        ),
    }
    return subprocess.run(
        [str(test_script), "coverage"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("backend_status", "frontend_status"),
    ((1, 0), (0, 1)),
)
def test_aggregate_coverage_fails_when_either_stage_fails(
    tmp_path: Path, backend_status: int, frontend_status: int
) -> None:
    result = _run_public_coverage(
        tmp_path,
        backend_status=backend_status,
        frontend_status=frontend_status,
        reports_to_create=("backend", "frontend"),
    )

    assert result.returncode == 1


def test_aggregate_coverage_succeeds_when_both_stages_succeed(
    tmp_path: Path,
) -> None:
    result = _run_public_coverage(
        tmp_path,
        backend_status=0,
        frontend_status=0,
        reports_to_create=("backend", "frontend"),
    )

    assert result.returncode == 0
    assert str(tmp_path / "run" / "coverage.xml") in result.stdout
    assert (
        str(tmp_path / "run" / "frontend" / "coverage" / "index.html")
        in result.stdout
    )
    assert (tmp_path / "coverage-stages.log").read_text(
        encoding="utf-8"
    ).splitlines() == [
        "backend:coverage",
        "frontend:run test:coverage -- --coverageReporters=text "
        "--coverageReporters=html "
        f"--coverageDirectory={tmp_path / 'run' / 'frontend' / 'coverage'}",
    ]


@pytest.mark.parametrize("missing_report", ("backend", "frontend"))
def test_aggregate_coverage_fails_when_required_report_is_missing(
    tmp_path: Path, missing_report: str
) -> None:
    present_report = "frontend" if missing_report == "backend" else "backend"
    result = _run_public_coverage(
        tmp_path,
        backend_status=0,
        frontend_status=0,
        reports_to_create=(present_report,),
    )

    assert result.returncode == 1
    missing_path = (
        tmp_path / "run" / "coverage.xml"
        if missing_report == "backend"
        else tmp_path / "run" / "frontend" / "coverage" / "index.html"
    )
    assert str(missing_path) not in result.stdout
    assert str(missing_path) in result.stderr


def test_aggregate_coverage_clears_stale_reports_before_running(
    tmp_path: Path,
) -> None:
    result = _run_public_coverage(
        tmp_path,
        backend_status=0,
        frontend_status=0,
        reports_to_create=(),
        stale_reports=("backend", "frontend"),
    )

    backend_report = tmp_path / "run" / "coverage.xml"
    frontend_directory = tmp_path / "run" / "frontend" / "coverage"
    frontend_report = frontend_directory / "index.html"
    assert result.returncode == 1
    assert str(backend_report) not in result.stdout
    assert str(frontend_report) not in result.stdout
    assert not backend_report.exists()
    assert not frontend_directory.exists()


def test_aggregate_coverage_stops_when_stale_report_cleanup_fails(
    tmp_path: Path,
) -> None:
    result = _run_public_coverage(
        tmp_path,
        backend_status=0,
        frontend_status=0,
        reports_to_create=("backend", "frontend"),
        block_backend_cleanup=True,
    )

    assert result.returncode != 0
    assert not (tmp_path / "coverage-stages.log").exists()


def _workflow(path: str) -> dict[str, object]:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _step(job: dict[str, object], name: str) -> dict[str, object]:
    steps = job["steps"]
    assert isinstance(steps, list)
    for step in steps:
        assert isinstance(step, dict)
        if step.get("name") == name:
            return step
    raise AssertionError(f"Workflow step not found: {name}")


def test_frontend_tests_runs_jest_coverage_and_requires_its_artifact() -> None:
    workflow = _workflow(".github/workflows/frontend-tests.yml")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs["test"]
    assert isinstance(job, dict)

    run_step = _step(job, "Run tests with coverage")
    assert str(run_step["run"]).startswith("npm run test:coverage")
    assert "--coverageReporters=text" in str(run_step["run"])
    assert "--coverageReporters=cobertura" in str(run_step["run"])
    assert "--coverageReporters=html" in str(run_step["run"])

    verify_step = _step(job, "Verify frontend coverage reports")
    assert "test -f coverage/cobertura-coverage.xml" in str(verify_step["run"])
    assert "test -f coverage/index.html" in str(verify_step["run"])

    upload_step = _step(job, "Upload coverage report")
    assert upload_step["uses"] == "actions/upload-artifact@v4"
    upload_options = upload_step["with"]
    assert isinstance(upload_options, dict)
    assert upload_options["if-no-files-found"] == "error"
    assert upload_options["path"] == "frontend/coverage/"


def test_coverage_workflow_requires_repository_owned_reports() -> None:
    workflow = _workflow(".github/workflows/coverage.yml")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)

    for job in jobs.values():
        assert isinstance(job, dict)
        steps = job["steps"]
        assert isinstance(steps, list)
        assert all(
            "codecov" not in str(step.get("uses", "")) for step in steps
        )

    backend_job = jobs["python-coverage"]
    assert isinstance(backend_job, dict)
    backend_upload = _step(backend_job, "Upload backend coverage artifact")
    backend_options = backend_upload["with"]
    assert isinstance(backend_options, dict)
    assert backend_options["path"] == "coverage.xml"
    assert backend_options["if-no-files-found"] == "error"

    # CI deduplication (#320) moved the frontend coverage run into the
    # frontend-tests workflow; the repository must still produce, verify,
    # and upload its own cobertura + html reports there.
    frontend_workflow = _workflow(".github/workflows/frontend-tests.yml")
    frontend_job = frontend_workflow["jobs"]["test"]
    assert isinstance(frontend_job, dict)
    frontend_run = _step(frontend_job, "Run tests with coverage")
    assert "--coverageReporters=cobertura" in str(frontend_run["run"])
    assert "--coverageReporters=html" in str(frontend_run["run"])
    frontend_verify = _step(frontend_job, "Verify frontend coverage reports")
    assert "coverage/cobertura-coverage.xml" in str(frontend_verify["run"])
    assert "coverage/index.html" in str(frontend_verify["run"])
    frontend_upload = _step(frontend_job, "Upload coverage report")
    frontend_options = frontend_upload["with"]
    assert isinstance(frontend_options, dict)
    assert frontend_options["path"] == "frontend/coverage/"
    assert frontend_options["if-no-files-found"] == "error"


def test_aggregate_coverage_reports_the_real_jest_html_path() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    coverage_body = script.split("run_coverage()", 1)[1].split(
        "run_security()", 1
    )[0]

    assert (
        'local frontend_report="$frontend_coverage_dir/index.html"'
        in coverage_body
    )
    assert '"$frontend_report"' in coverage_body
    assert "lcov-report/index.html" not in coverage_body


def test_maintained_backend_coverage_command_enforces_current_floor() -> None:
    runner = (ROOT / "scripts" / "run-maintained-backend-tests.sh").read_text(
        encoding="utf-8"
    )
    coverage_branch = runner.split("coverage)", 1)[1].split(";;", 1)[0]

    assert "--cov-fail-under=34" in coverage_branch


def test_aggregate_backend_coverage_uses_the_maintained_runner() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    coverage_body = script.split("run_coverage()", 1)[1].split(
        "run_security()", 1
    )[0]

    assert 'local backend_report="$TEST_RUN_DIR/coverage.xml"' in coverage_body
    assert (
        'COVERAGE_XML_PATH="$backend_report" '
        './scripts/run-maintained-backend-tests.sh coverage'
    ) in coverage_body
    assert "python -m pytest tests/" not in coverage_body
