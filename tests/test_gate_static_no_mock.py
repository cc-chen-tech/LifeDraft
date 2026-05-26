"""No-mock gate tests for static analysis configuration."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mypy_config_enables_strict_checks_for_changed_backend_code() -> None:
    config = (ROOT / "mypy.ini").read_text(encoding="utf-8")

    assert "strict = True" in config
    assert "warn_return_any = True" in config
    assert "warn_unused_configs = True" in config


def test_test_script_runs_mypy_in_strict_mode() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "MYPY_STRICT_TARGETS=(" in script
    assert "src/ai/text_quality.py" in script
    assert "src/services/music_service.py" in script
    assert "src/services/music_playlist_service.py" in script
    assert "src/services/story_tts_provider.py" in script
    assert "src/services/story_voice_reading.py" in script
    assert "src/services/story_voice_repository.py" in script
    assert "src/database/models.py" in script
    assert 'python -m mypy "${MYPY_STRICT_TARGETS[@]}" --strict' in script


def test_test_script_runs_music_frontend_queue_policy_tests() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "useMusicStore.musicQueuePolicy.test.ts" in script
    assert "improve-story-music-recommendation-and-premium-ai-queue" in script


def test_pr_workflows_skip_full_release_gates() -> None:
    heavy_workflows = [
        "coverage.yml",
        "e2e-tests.yml",
        "frontend-build.yml",
        "frontend-integration-tests.yml",
        "frontend-tests.yml",
    ]

    for filename in heavy_workflows:
        workflow = (ROOT / ".github" / "workflows" / filename).read_text(encoding="utf-8")
        assert "pull_request:" not in workflow, f"{filename} should not run for every PR"
        assert "push:" in workflow
        assert "branches: [main]" in workflow


def test_backend_workflow_runs_light_gate_on_pr_and_full_suite_on_main() -> None:
    workflow = (ROOT / ".github" / "workflows" / "backend-tests.yml").read_text(
        encoding="utf-8"
    )

    assert "pull_request:" in workflow
    assert "Run maintained backend gates for PR" in workflow
    assert "if: github.event_name == 'pull_request'" in workflow
    assert "Run full backend suite before main release" in workflow
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/main'" in workflow
    assert "python -m pytest tests -q" in workflow


def test_production_deploy_waits_for_main_release_gates() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-production.yml").read_text(
        encoding="utf-8"
    )

    for required in (
        "'Backend Tests'",
        "'Frontend Build'",
        "'Frontend Tests'",
        "'Frontend Integration Tests'",
        "'Coverage Report'",
        "'E2E Tests'",
    ):
        assert required in workflow
    assert 'workflows: ["E2E Tests"]' in workflow


def test_gate_tests_do_not_use_skip_or_mocking_constructs() -> None:
    gate_files = sorted((ROOT / "tests").glob("test_gate_*.py"))
    assert gate_files, "Expected gate test files to exist"

    banned_tokens = tuple(
        "".join(parts)
        for parts in (
            ("@pytest.mark.", "skip"),
            ("pytest.", "skip"),
            ("@pytest.mark.", "xfail"),
            ("unittest.", "mock"),
            ("Mo", "ck("),
            ("Magic", "Mock"),
            ("pa", "tch("),
        )
    )
    for path in gate_files:
        text = path.read_text(encoding="utf-8")
        for token in banned_tokens:
            assert token not in text, f"{path.name} uses banned test construct: {token}"
