"""Execute release gate JavaScript against controlled GitHub API responses."""

import json
from pathlib import Path
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "event,trigger,bypass,smoke,allowed",
    [
        ("workflow_run", "E2E Tests", False, None, True),
        ("workflow_run", "Model Smoke", False, "success", True),
        ("workflow_run", "Model Smoke", False, "failure", False),
        ("workflow_dispatch", "", True, "failure", False),
        ("workflow_dispatch", "", True, "success", True),
        ("workflow_dispatch", "", True, None, False),
    ],
)
def test_release_gate_requires_smoke_for_every_deployment(event, trigger, bypass, smoke, allowed):
    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy-production.yml").read_text())
    script = workflow["jobs"]["verify-ci"]["steps"][1]["with"]["script"]
    script = script.replace("${{ github.event_name }}", event)
    script = script.replace("${{ inputs.force_after_local_preflight }}", str(bypass).lower())
    script = script.replace("${{ steps.resolve.outputs.deploy_sha }}", "candidate")
    names = [
        "Backend Tests", "Python Code Quality", "Frontend Build", "Frontend Code Quality",
        "Frontend Tests", "Coverage Report", "CI", "Wiki Check", "E2E Tests",
    ]
    runs = [{"name": name, "status": "completed", "conclusion": "success"} for name in names]
    smoke_runs = [] if smoke is None else [
        {"name": "Model Smoke", "head_sha": "candidate", "status": "completed", "conclusion": smoke}
    ]
    harness = """
const context = {repo: {owner: 'test', repo: 'test'}, payload: {workflow_run: {name: TRIGGER}}};
const core = {warning() {}, info() {}};
let clock = 0;
Date.now = () => (clock += 1000000);
const github = {rest: {actions: {
  listWorkflowRunsForRepo: async () => ({data: {workflow_runs: RUNS}}),
  listWorkflowRuns: async () => ({data: {workflow_runs: SMOKE}}),
}}};
(async () => { SCRIPT })().then(() => process.exit(0)).catch(() => process.exit(1));
"""
    for token, value in [("TRIGGER", json.dumps(trigger)), ("RUNS", json.dumps(runs)),
                         ("SMOKE", json.dumps(smoke_runs)), ("SCRIPT", script)]:
        harness = harness.replace(token, value)
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=10)
    assert (result.returncode == 0) is allowed, result.stderr
