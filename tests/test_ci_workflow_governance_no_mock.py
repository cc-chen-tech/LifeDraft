"""Contracts for the public quick gate and GitHub workflow ownership."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
DEPLOY_WORKFLOW = WORKFLOW_DIR / "deploy-production.yml"
INTEGRATION_WORKFLOW = WORKFLOW_DIR / "frontend-integration-tests.yml"
FRONTEND_WORKFLOW = WORKFLOW_DIR / "frontend-tests.yml"
COVERAGE_WORKFLOW = WORKFLOW_DIR / "coverage.yml"
E2E_WORKFLOW = WORKFLOW_DIR / "e2e-tests.yml"


def _load_workflow(path: Path) -> dict[str, object]:
    workflow = yaml.load(
        path.read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert isinstance(workflow, dict)
    return workflow


def _non_deploy_workflows() -> list[Path]:
    return sorted(
        path
        for path in WORKFLOW_DIR.glob("*.yml")
        if path != DEPLOY_WORKFLOW
    )


def _quick_probe(
    failed_gate: str,
    trace_path: Path,
) -> subprocess.CompletedProcess[str]:
    script = r'''
source ./test.sh
record_gate() {
    printf '%s\n' "$1" >> "$TRACE_PATH"
    if [ "$FAILED_GATE" = "$1" ]; then
        return 9
    fi
    return 0
}
run_mypy() { record_gate mypy; }
run_maintained_backend_suite() { record_gate backend; }
run_frontend_strict_typecheck() { record_gate typescript; }
run_preflight_jest() { record_gate jest; }
run_quick >/dev/null 2>&1
'''
    return subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env={
            **os.environ,
            "FAILED_GATE": failed_gate,
            "TRACE_PATH": str(trace_path),
        },
        capture_output=True,
        text=True,
        check=False,
    )


def _quick_trace(trace_path: Path) -> list[str]:
    if not trace_path.exists():
        return []
    return trace_path.read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize(
    "failed_gate",
    ["mypy", "backend", "typescript", "jest"],
)
def test_quick_gate_propagates_each_failure(
    failed_gate: str,
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "quick-trace"
    result = _quick_probe(failed_gate, trace_path)

    assert result.returncode != 0
    assert _quick_trace(trace_path) == [
        "mypy",
        "backend",
        "typescript",
        "jest",
    ]


def test_quick_gate_succeeds_in_required_order(tmp_path: Path) -> None:
    trace_path = tmp_path / "quick-trace"
    result = _quick_probe("", trace_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _quick_trace(trace_path) == [
        "mypy",
        "backend",
        "typescript",
        "jest",
    ]
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    assert "quick)" in script
    assert "quick          -" in script
    maintained_runner = (
        ROOT / "scripts" / "run-maintained-backend-tests.sh"
    ).read_text(encoding="utf-8")
    assert "tests/test_ci_workflow_governance_no_mock.py" in maintained_runner


def _function_body(script: str, function_name: str) -> str:
    match = re.search(
        rf"^{re.escape(function_name)}\(\) \{{\n(.*?)^\}}$",
        script,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, function_name
    return match.group(1)


def test_quick_helpers_retain_their_authoritative_commands() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    mypy_body = _function_body(script, "run_mypy")
    backend_body = _function_body(script, "run_maintained_backend_suite")
    typescript_body = _function_body(
        script,
        "run_frontend_strict_typecheck",
    )
    jest_body = _function_body(script, "run_preflight_jest")

    assert "python -m mypy" in mypy_body
    assert "--strict" in mypy_body
    assert "tests/test_gate_static_no_mock.py" in mypy_body
    assert "./scripts/run-maintained-backend-tests.sh test" in backend_body
    assert "npx tsc --noEmit --strict" in typescript_body
    assert "npx jest" in jest_body
    assert "--runInBand" in jest_body
    assert jest_body.count("src/__tests__/") == 19
    for required_test in (
        "src/__tests__/preflight/storyContinuityPreflight.test.tsx",
        "src/__tests__/lib/sse.test.ts",
        "src/__tests__/lib/sessionRecovery.test.ts",
        "src/__tests__/pages/CreatePage.test.tsx",
        "src/__tests__/pages/PlayPage.test.tsx",
        "src/__tests__/components/ChatBar.test.tsx",
        "src/__tests__/app/api/route.test.ts",
        "src/__tests__/stores/useCollectionStore.test.ts",
    ):
        assert required_test in jest_body


def test_frontend_tests_owns_full_jest_coverage_and_artifact() -> None:
    workflows = _non_deploy_workflows()
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in workflows
    )
    frontend_text = FRONTEND_WORKFLOW.read_text(encoding="utf-8")
    coverage = _load_workflow(COVERAGE_WORKFLOW)

    assert not INTEGRATION_WORKFLOW.exists()
    assert workflow_text.count("npm run test:coverage") == 1
    assert "npm run test:unit" not in workflow_text
    assert "npm run test:integration" not in workflow_text
    assert workflow_text.count("frontend-coverage-report") == 1
    assert "--coverageReporters=cobertura" in frontend_text
    assert "test -f coverage/cobertura-coverage.xml" in frontend_text
    assert "test -f coverage/index.html" in frontend_text
    assert "./test.sh quick" in E2E_WORKFLOW.read_text(encoding="utf-8")
    jobs = coverage["jobs"]
    assert isinstance(jobs, dict)
    assert set(jobs) == {"python-coverage"}


def test_deployment_required_workflows_match_active_workflows() -> None:
    active_names = {
        str(_load_workflow(path)["name"])
        for path in _non_deploy_workflows()
    }
    deploy_text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    required_match = re.search(
        r"const requiredWorkflows = \[(.*?)\];",
        deploy_text,
        re.DOTALL,
    )
    assert required_match is not None
    required_names = set(re.findall(r"'([^']+)'", required_match.group(1)))

    assert required_names == active_names
    assert "Frontend Integration Tests" not in required_names
    assert {
        "Frontend Tests",
        "Coverage Report",
        "E2E Tests",
    }.issubset(required_names)


def test_pr_quick_gate_precedes_e2e_environment_and_playwright() -> None:
    workflow = _load_workflow(E2E_WORKFLOW)
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs["e2e-tests"]
    assert isinstance(job, dict)
    steps = job["steps"]
    assert isinstance(steps, list)
    named_steps = {
        str(step["name"]): (index, step)
        for index, step in enumerate(steps)
        if isinstance(step, dict) and "name" in step
    }

    quick_index, quick_step = named_steps["Run PR quick gate"]
    env_index, _ = named_steps["Create .env file"]
    browser_index, _ = named_steps["Install Playwright browsers"]
    e2e_index, _ = named_steps["Run E2E tests"]
    assert quick_step["run"] == "./test.sh quick"
    assert quick_step["if"] == "github.event_name == 'pull_request'"
    assert quick_index < env_index < browser_index < e2e_index


def test_every_non_deploy_workflow_cancels_only_obsolete_pr_runs() -> None:
    expected_group = (
        "${{ github.workflow }}-"
        "${{ github.event.pull_request.number || github.sha }}"
    )
    expected_cancel = "${{ github.event_name == 'pull_request' }}"

    for path in _non_deploy_workflows():
        workflow = _load_workflow(path)
        concurrency = workflow.get("concurrency")
        assert isinstance(concurrency, dict), path.name
        assert concurrency.get("group") == expected_group, path.name
        assert (
            concurrency.get("cancel-in-progress") == expected_cancel
        ), path.name
