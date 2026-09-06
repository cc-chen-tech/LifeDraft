from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pr_quick_gate_uses_frontend_only_runner():
    workflow = (PROJECT_ROOT / ".github/workflows/e2e-tests.yml").read_text()
    runner = (PROJECT_ROOT / "test.sh").read_text()

    assert "run: ./test.sh quick-frontend" in workflow
    assert "run: ./test.sh quick\n" not in workflow
    assert "run_quick_frontend()" in runner


def test_backend_workflow_owns_backend_quick_gates():
    workflow = (PROJECT_ROOT / ".github/workflows/backend-tests.yml").read_text()

    assert "./test.sh mypy" in workflow
    assert "./scripts/run-maintained-backend-tests.sh test" in workflow
