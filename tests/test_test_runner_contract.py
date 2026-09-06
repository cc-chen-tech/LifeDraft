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


def test_pytest_module_reset_preserves_schema_without_drop_all():
    conftest = (PROJECT_ROOT / "tests/conftest.py").read_text()
    module_reset = conftest.split(
        "def _reset_isolated_db_per_module", 1
    )[1].split("@pytest.fixture", 1)[0]

    assert "def _clear_isolated_db" in conftest
    assert "Base.metadata.drop_all(engine)" not in module_reset
    assert "sqlite_sequence" in conftest


def test_background_job_state_has_one_restore_fixture():
    conftest = (PROJECT_ROOT / "tests/conftest.py").read_text()

    assert conftest.count("sse_helpers._background_jobs_enabled = True") == 1


def test_unit_runner_excludes_slow_and_exposes_slow_command():
    runner = (PROJECT_ROOT / "test.sh").read_text()

    assert "tests/ -m 'unit and not slow' -v" in runner
    assert "run_slow()" in runner
    assert "slow)" in runner


def test_large_context_regression_is_explicitly_slow():
    source = (PROJECT_ROOT / "tests/test_long_story_context.py").read_text()

    assert "pytest.mark.slow" in source.split("pytestmark", 1)[1].split("\n", 1)[0]


def test_timing_regressions_use_controlled_progression():
    opening = (PROJECT_ROOT / "tests/test_opening_story_contract.py").read_text()
    sse = (PROJECT_ROOT / "tests/test_sse_timeout_integration.py").read_text()
    cache = (PROJECT_ROOT / "tests/test_cache_management.py").read_text()

    assert "time.sleep(6)" not in opening
    assert "time.sleep(0.05)" not in opening
    assert "stop_event.wait(timeout=10)" not in sse
    assert "time.sleep(0.05)" not in sse
    assert "time.sleep(" not in cache


def test_recovered_contracts_are_not_hidden_by_stale_xfails():
    recovered_sources = [
        (PROJECT_ROOT / "tests/test_soft_narrative_length_recovery.py").read_text(),
        (PROJECT_ROOT / "tests/test_story_generation_failure_integrity.py").read_text(),
        (PROJECT_ROOT / "tests/test_security_sse_auth_contract.py").read_text(),
    ]

    assert all("origin/main drift" not in source for source in recovered_sources)
    assert all("当前使用 get_current_user_optional" not in source for source in recovered_sources)
