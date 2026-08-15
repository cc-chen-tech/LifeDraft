"""Behavior and workflow contracts for truthful coverage gates."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def _finish_coverage_run(
    tmp_path: Path,
    *,
    backend_status: int,
    frontend_status: int,
    reports_to_create: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    backend_report = tmp_path / "backend" / "index.html"
    frontend_report = tmp_path / "frontend" / "index.html"
    reports = {"backend": backend_report, "frontend": frontend_report}
    for report_name in reports_to_create:
        report = reports[report_name]
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("coverage", encoding="utf-8")

    environment = {
        **os.environ,
        "TEST_SCRIPT": str(ROOT / "test.sh"),
        "BACKEND_STATUS": str(backend_status),
        "FRONTEND_STATUS": str(frontend_status),
        "BACKEND_REPORT": str(backend_report),
        "FRONTEND_REPORT": str(frontend_report),
    }
    return subprocess.run(
        [
            "bash",
            "-c",
            'source "$TEST_SCRIPT"; finish_coverage_run '
            '"$BACKEND_STATUS" "$FRONTEND_STATUS" '
            '"$BACKEND_REPORT" "$FRONTEND_REPORT"',
        ],
        cwd=ROOT,
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
    result = _finish_coverage_run(
        tmp_path,
        backend_status=backend_status,
        frontend_status=frontend_status,
        reports_to_create=("backend", "frontend"),
    )

    assert result.returncode == 1


def test_aggregate_coverage_succeeds_when_both_stages_succeed(
    tmp_path: Path,
) -> None:
    result = _finish_coverage_run(
        tmp_path,
        backend_status=0,
        frontend_status=0,
        reports_to_create=("backend", "frontend"),
    )

    assert result.returncode == 0
    assert str(tmp_path / "backend" / "index.html") in result.stdout
    assert str(tmp_path / "frontend" / "index.html") in result.stdout


def test_aggregate_coverage_reports_only_files_that_exist(
    tmp_path: Path,
) -> None:
    result = _finish_coverage_run(
        tmp_path,
        backend_status=0,
        frontend_status=0,
        reports_to_create=("frontend",),
    )

    assert result.returncode == 0
    assert str(tmp_path / "backend" / "index.html") not in result.stdout
    assert str(tmp_path / "frontend" / "index.html") in result.stdout


def test_aggregate_coverage_clears_stale_reports_before_running(
    tmp_path: Path,
) -> None:
    backend_report = tmp_path / "coverage.xml"
    frontend_directory = tmp_path / "frontend" / "coverage"
    frontend_report = frontend_directory / "index.html"
    backend_report.write_text("stale", encoding="utf-8")
    frontend_directory.mkdir(parents=True)
    frontend_report.write_text("stale", encoding="utf-8")

    environment = {
        **os.environ,
        "TEST_SCRIPT": str(ROOT / "test.sh"),
        "BACKEND_REPORT": str(backend_report),
        "FRONTEND_DIRECTORY": str(frontend_directory),
        "FRONTEND_REPORT": str(frontend_report),
    }
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$TEST_SCRIPT"; '
            'prepare_coverage_run "$BACKEND_REPORT" "$FRONTEND_DIRECTORY"; '
            'finish_coverage_run 0 0 "$BACKEND_REPORT" "$FRONTEND_REPORT"',
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert str(backend_report) not in result.stdout
    assert str(frontend_report) not in result.stdout
    assert not backend_report.exists()
    assert not frontend_directory.exists()


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

    frontend_job = jobs["frontend-coverage"]
    assert isinstance(frontend_job, dict)
    frontend_run = _step(frontend_job, "Run Jest with coverage")
    assert "--coverageReporters=cobertura" in str(frontend_run["run"])
    assert "--coverageReporters=html" in str(frontend_run["run"])
    frontend_verify = _step(frontend_job, "Verify frontend coverage reports")
    assert "coverage/cobertura-coverage.xml" in str(frontend_verify["run"])
    assert "coverage/index.html" in str(frontend_verify["run"])
    frontend_upload = _step(frontend_job, "Upload frontend coverage artifact")
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
