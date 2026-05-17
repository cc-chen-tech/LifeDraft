"""Early no-mock checks that should fail before slower DB/E2E layers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGE_DIR = ROOT / "openspec" / "changes" / "fix-story-continuity-history-media"


def test_fix_story_continuity_change_tasks_stay_complete() -> None:
    tasks = (CHANGE_DIR / "tasks.md").read_text(encoding="utf-8")

    assert "- [ ]" not in tasks
    assert tasks.count("- [x]") == 34
    assert "7.1 Add frontend no-skip regression coverage for `/story/opening`" in tasks
    assert "8.8 Run targeted regression tests and `./test.sh all`." in tasks


def test_preflight_script_runs_before_expensive_layers() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "run_preflight" in script
    assert "openspec validate fix-story-continuity-history-media --strict" in script
    assert "openspec validate add-story-voice-reading --strict" in script
    assert "openspec validate shift-left-e2e-contract-gates --strict" in script
    assert "npx tsc --noEmit --strict" in script
    assert "tests/test_gate_preflight_no_mock.py" in script
    assert "tests/test_gate_gameplay_behavior_no_mock.py" in script
    assert "tests/test_gate_contracts_no_mock.py" in script
    assert "tests/test_music_degradation_no_mock.py" in script
    assert "tests/test_shift_left_e2e_contract_no_mock.py" in script
    assert "storyContinuityPreflight.test.tsx" in script
    assert "src/__tests__/lib/sse.test.ts" in script
    assert script.index("run_preflight || ((failed++))") < script.index("run_mypy || ((failed++))")
    assert script.index("run_preflight || ((failed++))") < script.index(
        "run_e2e_browser || ((failed++))"
    )


def test_frontend_regression_fixture_exercises_changed_surfaces() -> None:
    fixture = (ROOT / "frontend" / "src" / "app" / "e2e-regression" / "page.tsx").read_text(
        encoding="utf-8"
    )
    e2e = (ROOT / "frontend" / "e2e" / "no-mock-regression.spec.ts").read_text(encoding="utf-8")

    for token in (
        "streamed-story",
        "history-scene-image-state",
        "collection-refresh-state",
        "OptionCards",
        "ChatBar",
    ):
        assert token in fixture

    for test_name in (
        "stream retry replaces active story attempt instead of duplicating it",
        "history review stays pinned to selected round with matching scene image state",
        "collection panel keeps data visible during background refresh",
    ):
        assert test_name in e2e


def test_frontend_image_generation_path_is_checked_before_e2e() -> None:
    api_source = (ROOT / "frontend" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert (
        "fetchJson<{ images: Array<{ image_id: number; image_url: string }>; total: number }>('/images/generate'"
        in api_source
    )
    assert "fetchJson('/images'" not in api_source


def test_ai_heavy_e2e_specs_do_not_override_project_timeout_too_low() -> None:
    spec = (ROOT / "frontend" / "e2e" / "claude-code-improvements.spec.ts").read_text(
        encoding="utf-8"
    )

    assert "test.setTimeout(120_000)" not in spec
    assert "test.setTimeout(300_000)" in spec
