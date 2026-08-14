"""Contracts for hermetic, single-sourced test gates."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_maintained_backend_manifest_is_shared_by_both_ci_workflows() -> None:
    runner = (ROOT / "scripts" / "run-maintained-backend-tests.sh").read_text(
        encoding="utf-8"
    )
    coverage_workflow = (ROOT / ".github" / "workflows" / "coverage.yml").read_text(
        encoding="utf-8"
    )
    backend_workflow = (
        ROOT / ".github" / "workflows" / "backend-tests.yml"
    ).read_text(encoding="utf-8")

    assert "maintained_tests=(" in runner
    assert "test_gate_preflight_no_mock.py" in runner
    assert "test_story_voice_chapter_contract.py" in runner
    assert "test_music_runtime_removed.py" in runner
    assert '"${maintained_tests[@]}" -v --tb=short' in runner
    assert 'coverage_xml_path="${COVERAGE_XML_PATH:-coverage.xml}"' in runner
    assert '--cov=src --cov-report="xml:${coverage_xml_path}" --cov-report=term' in runner
    assert "./scripts/run-maintained-backend-tests.sh coverage" in coverage_workflow
    assert "./scripts/run-maintained-backend-tests.sh test" in backend_workflow
    assert "tests/test_gate_preflight_no_mock.py" not in coverage_workflow
    assert "tests/test_gate_preflight_no_mock.py" not in backend_workflow


def test_preflight_openapi_drift_check_uses_run_directory_artifacts() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "ensure_test_dirs" in script.split("run_preflight()", 1)[1].split(
        "run_mypy()", 1
    )[0]
    assert 'local openapi_check_dir="$TEST_RUN_DIR/openapi-check"' in script
    assert 'python scripts/export_openapi.py "$generated_openapi_schema"' in script
    assert 'npx openapi-typescript "$generated_openapi_schema" -o "$generated_openapi_types"' in script
    assert 'cmp -s "$generated_openapi_schema" frontend/src/types/openapi-schema.json' in script
    assert 'cmp -s "$generated_openapi_types" frontend/src/types/api-generated.d.ts' in script
    assert "git diff --exit-code -- frontend/src/types/openapi-schema.json" not in script


def test_browser_gate_runs_core_once_and_only_selects_ai_heavy_followups() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    e2e_body = script.split("run_e2e_browser_impl()", 1)[1].split("run_coverage()", 1)[0]

    assert e2e_body.count('run_playwright_command "') == 2
    assert 'run_playwright_command "core" npx playwright test --project=core' in e2e_body
    assert 'run_playwright_command "music-player"' not in e2e_body
    assert 'run_playwright_command "character-settings"' in e2e_body
    for duplicated_core_label in (
        "realistic-style-alignment",
        "accessible-control-names",
        "world-fact-safety",
        "opening-visible-completion",
        "entity-collection-reliability",
        "audio-regeneration-state",
        "life-summary-grounding",
        "fast-generation-budget",
        "story-voice",
        "minimax-audio",
        "collection-recognition",
    ):
        assert f'run_playwright_command "{duplicated_core_label}"' not in e2e_body


def test_frontend_coverage_excludes_test_source_directories() -> None:
    config = (ROOT / "frontend" / "jest.config.js").read_text(encoding="utf-8")

    assert "'src/**/*.{ts,tsx}'" in config
    assert "'!src/**/__tests__/**'" in config
