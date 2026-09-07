"""Real CLI startup must fail closed with a report, without PYTHONPATH."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import model_smoke


def test_missing_audio_runtime_fails_before_model_initialization(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("MODEL_SMOKE_ENABLED", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
    monkeypatch.setenv("MINIMAX_API_KEY", "offline-placeholder")
    for name in ("E2E_DETERMINISTIC_STORY", "MINIMAX_E2E_LOCAL_AUDIO", "MINIMAX_E2E_LOCAL_IMAGE"):
        monkeypatch.setenv(name, "0")
    with pytest.raises(FileNotFoundError, match="ffmpeg"):
        model_smoke.run(tmp_path / "report.json", tmp_path / "assets", None)


def test_generator_and_game_public_exports_import_in_fresh_process():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", "from src.ai.generator import EventGenerator; "
         "from src.game import GameLoop, PlayerState, assign_sexual_orientation"],
        cwd=root, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_error_report_survives_unavailable_telemetry(monkeypatch):
    monkeypatch.setitem(sys.modules, "src.observability.model_telemetry", None)
    error = RuntimeError("private prompt and API key must never be reported")
    assert model_smoke._safe_error(error) == {
        "error_kind": "unknown", "error_message": "RuntimeError",
    }


def test_direct_cli_without_credentials_writes_safe_failure_report(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/model_smoke.py"
    report = tmp_path / "evidence" / "smoke-summary.json"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("MODEL_SMOKE_ENABLED", None)
    result = subprocess.run(
        [sys.executable, str(script), "--report", str(report)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    payload = json.loads(report.read_text())
    assert payload["status"] == "failed"
    assert payload["errors"] == ["smoke_runner_failed"]
    assert payload["runner_error"]["error_message"] == "RuntimeError"
    assert json.loads(result.stdout)["errors"] == ["smoke_runner_failed"]
