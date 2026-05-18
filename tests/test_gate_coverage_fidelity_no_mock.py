"""Coverage gate fidelity checks for maintained backend tests."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _python_tests_from_block(script: str, function_name: str) -> set[str]:
    match = re.search(rf"{function_name}\(\) \{{(?P<body>.*?)\n\}}", script, re.S)
    assert match, f"Could not find {function_name} in test.sh"
    return set(re.findall(r"tests/[A-Za-z0-9_/\.-]+\.py", match.group("body")))


def _frontend_tests_from_block(script: str, function_name: str) -> set[str]:
    match = re.search(rf"{function_name}\(\) \{{(?P<body>.*?)\n\}}", script, re.S)
    assert match, f"Could not find {function_name} in test.sh"
    return set(
        re.findall(
            r"src/__tests__/[A-Za-z0-9_/\.-]+\.(?:test|spec)\.tsx?",
            match.group("body"),
        )
    )


def test_maintained_backend_coverage_includes_test_sh_backend_gates() -> None:
    """Coverage CI must not silently omit maintained backend gate tests."""

    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    coverage_workflow = (ROOT / ".github" / "workflows" / "coverage.yml").read_text(
        encoding="utf-8"
    )

    maintained_tests = set()
    for function_name in (
        "run_preflight",
        "run_mypy",
        "run_imports",
        "run_contract",
        "run_db",
    ):
        maintained_tests.update(_python_tests_from_block(script, function_name))

    omitted = sorted(test for test in maintained_tests if test not in coverage_workflow)

    assert not omitted, (
        "Maintained backend coverage must include every backend test wired into "
        f"test.sh preflight/mypy/imports/contract/db. Missing: {omitted}"
    )


def test_coverage_workflow_names_maintained_backend_scope() -> None:
    """Coverage labels must make the maintained subset explicit."""

    coverage_workflow = (ROOT / ".github" / "workflows" / "coverage.yml").read_text(
        encoding="utf-8"
    )

    assert "Maintained Backend Coverage" in coverage_workflow
    assert "maintained-backend-coverage" in coverage_workflow


def test_maintained_backend_threshold_has_reached_first_ratchet() -> None:
    """The first stable promotion batch should keep the maintained threshold at 30%."""

    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    coverage_workflow = (ROOT / ".github" / "workflows" / "coverage.yml").read_text(
        encoding="utf-8"
    )

    assert "--cov-fail-under=30" in script
    assert "--cov-fail-under=30" in coverage_workflow
    assert "--cov-fail-under=25" not in script
    assert "--cov-fail-under=25" not in coverage_workflow


def test_backend_workflow_includes_promoted_high_risk_groups() -> None:
    """Maintained backend CI should run the promoted gameplay/media/SSE groups."""

    backend_workflow = (
        ROOT / ".github" / "workflows" / "backend-tests.yml"
    ).read_text(encoding="utf-8")

    required = {
        "tests/test_api_gameplay.py",
        "tests/test_frontend_backend_field_contracts.py",
        "tests/test_images_router.py",
        "tests/test_api_collection.py",
        "tests/test_scene_image_sse_contract.py",
        "tests/test_collection_cache_contract.py",
        "tests/test_session_cache.py",
        "tests/test_sse_helpers.py",
    }

    missing = sorted(test for test in required if test not in backend_workflow)
    assert not missing, f"Promoted maintained backend tests missing from CI: {missing}"


def test_test_coverage_change_is_validated_in_preflight() -> None:
    """This change's own OpenSpec contract must run before expensive layers."""

    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "openspec validate harden-test-coverage-and-gate-fidelity --strict" in script


def test_browser_regression_change_is_validated_in_preflight() -> None:
    """Browser exploration codification must stay in the maintained preflight."""

    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "openspec validate codify-browser-exploration-regressions --strict" in script


def test_backend_legacy_restoration_change_is_validated_in_preflight() -> None:
    """Legacy backend restoration OpenSpec contract must stay in preflight."""

    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "openspec validate restore-backend-legacy-contracts --strict" in script


def test_frontend_backend_field_contract_change_is_validated_in_preflight() -> None:
    """Frontend/backend field contract OpenSpec must stay in preflight."""

    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "openspec validate harden-frontend-backend-field-contracts --strict" in script


def test_router_collection_promotion_change_is_validated_in_preflight() -> None:
    """Router and collection promotion OpenSpec must stay in preflight."""

    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "openspec validate promote-router-collection-maintained-gates --strict" in script


def test_frontend_backend_field_contract_file_is_wired() -> None:
    """Field drift tests must run in both preflight and contract gates."""

    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    preflight_tests = _python_tests_from_block(script, "run_preflight")
    contract_tests = _python_tests_from_block(script, "run_contract")

    assert "tests/test_frontend_backend_field_contracts.py" in preflight_tests
    assert "tests/test_frontend_backend_field_contracts.py" in contract_tests


def test_router_collection_promotion_files_are_wired() -> None:
    """Promoted router and collection suites must run in maintained gates."""

    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    preflight_tests = _python_tests_from_block(script, "run_preflight")
    contract_tests = _python_tests_from_block(script, "run_contract")
    coverage_tests = _python_tests_from_block(
        script, "run_coverage_maintained_backend"
    )

    required = {
        "tests/test_images_router.py",
        "tests/test_api_collection.py",
    }

    assert required <= preflight_tests
    assert required <= contract_tests
    assert required <= coverage_tests


def test_browser_regression_preflight_file_is_wired() -> None:
    """New browser-agent regression tests must not be left out of preflight."""

    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    frontend_preflight_tests = _frontend_tests_from_block(script, "run_preflight")

    required = {
        "src/__tests__/preflight/storyContinuityPreflight.test.tsx",
        "src/__tests__/preflight/browserExplorationRegressionPreflight.test.tsx",
    }

    assert required <= frontend_preflight_tests


def test_story101_deep_exploration_is_discoverable_from_e2e_gate() -> None:
    """The manual deep browser sweep must remain reachable from test.sh e2e."""

    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "STORY101_DEEP_EXPLORATION" in script
    assert "e2e/story101-exploration.spec.ts" in script
