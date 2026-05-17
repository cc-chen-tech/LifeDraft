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
    assert "src/services/story_voice_reading.py" in script
    assert "src/services/story_voice_repository.py" in script
    assert "src/database/models.py" in script
    assert 'python -m mypy "${MYPY_STRICT_TARGETS[@]}" --strict' in script


def test_test_script_runs_music_frontend_queue_policy_tests() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "useMusicStore.musicQueuePolicy.test.ts" in script
    assert "improve-story-music-recommendation-and-premium-ai-queue" in script


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
