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


def test_runner_exposes_accurate_scope_commands():
    runner = (PROJECT_ROOT / "test.sh").read_text()

    assert "run_acceptance()" in runner
    assert "run_full_backend()" in runner
    assert "acceptance|all|\"\")" in runner
    assert "full-backend)" in runner
    assert "e2e-core)" in runner
    assert "e2e-full)" in runner
    assert "all|\"\")" in runner


def test_e2e_workflow_separates_pr_core_and_scheduled_full_runs():
    workflow = (PROJECT_ROOT / ".github/workflows/e2e-tests.yml").read_text()

    assert "schedule:" in workflow
    assert "run: ./test.sh e2e-core" in workflow
    assert "run: ./test.sh e2e-full" in workflow


def test_playwright_ci_reporter_keeps_console_and_html_reports():
    config = (PROJECT_ROOT / "frontend/playwright.config.ts").read_text()

    assert "['line']" in config or "['list']" in config
    assert "['html'" in config
    assert "open: 'never'" in config
