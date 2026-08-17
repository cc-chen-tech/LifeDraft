"""No-mock gate tests for static analysis configuration."""

from pathlib import Path
import pytest

pytestmark = [pytest.mark.unit]


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
    assert "src/services/story_tts_provider.py" in script
    assert "src/services/minimax_config.py" in script
    assert "src/services/minimax_story_tts_provider.py" in script
    assert "src/services/story_voice_reading.py" in script
    assert "src/services/story_voice_repository.py" in script
    assert "src/database/models.py" in script
    assert "src/services/daily_recommended_prefetch.py" in script
    assert "src/services/daily_recommended_prefetch_repository.py" in script
    assert 'python -m mypy "${MYPY_STRICT_TARGETS[@]}" --strict' in script


def test_test_script_does_not_run_retired_music_contracts() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "useMusicStore.musicQueuePolicy.test.ts" not in script
    assert "improve-story-music-recommendation-and-premium-ai-queue" not in script
    assert "tests/test_music_runtime_removed.py" in script


def test_test_script_runs_minimax_audio_generation_frontend_tests() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    config = (ROOT / "frontend" / "playwright.config.ts").read_text(encoding="utf-8")

    assert 'run_playwright_command "core" npx playwright test --project=core' in script
    assert "minimax-story-audio-generation.spec.ts" not in config.split(
        "const AI_HEAVY_TESTS", 1
    )[1].split("const MANUAL_EXPLORATION_TESTS", 1)[0]
    assert "tests/test_story_voice_chapter_contract.py" in script
    assert "tests/test_story_voice_async_chapter.py" in script


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
