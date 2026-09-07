import json
import logging
from pathlib import Path

import pytest

from scripts import model_smoke


def test_model_smoke_requires_explicit_real_provider_mode(monkeypatch):
    monkeypatch.delenv("MODEL_SMOKE_ENABLED", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-live-openai")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-live-minimax")

    with pytest.raises(RuntimeError, match="MODEL_SMOKE_ENABLED"):
        model_smoke._require_real_credentials()

    monkeypatch.setenv("MODEL_SMOKE_ENABLED", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-for-testing")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        model_smoke._require_real_credentials()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-live-openai")
    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    with pytest.raises(RuntimeError, match="E2E_DETERMINISTIC_STORY"):
        model_smoke._require_real_credentials()


def test_model_smoke_report_schema_is_payload_free():
    checks = [
        {
            "name": "text_generation_and_constraints",
            "provider": "openai-compatible",
            "model": "test-model",
            "outcome": "passed",
            "duration_ms": 12.5,
        }
    ]
    events = [
        {
            "outcome": "success",
            "fallback_from": None,
            "error_kind": None,
            "phase": "provider",
        },
        {
            "outcome": "failure",
            "fallback_from": None,
            "error_kind": "rate_limit",
            "phase": "provider",
        },
    ]

    report = model_smoke._build_report(checks, events, "2026-09-06T00:00:00Z")

    assert report["schema_version"] == 1
    assert report["status"] == "passed"
    assert report["fixture"] == model_smoke.FIXTURE_PREFIX
    assert set(report) == {
        "schema_version",
        "status",
        "started_at",
        "finished_at",
        "fixture",
        "checks",
        "warnings",
        "errors",
        "model_events",
    }
    assert report["warnings"] == ["provider_retry_observed"]
    assert report["model_events"] == {
        "count": 2,
        "success_count": 1,
        "failure_count": 1,
        "fallback_count": 0,
        "unknown_error_count": 0,
    }
    serialized = json.dumps(report)
    assert "prompt" not in serialized
    assert "response" not in serialized
    assert "story text" not in serialized


def test_model_smoke_writes_provider_events_as_jsonl(tmp_path):
    event_path = tmp_path / "model-events.jsonl"
    collector = model_smoke.ModelEventCollector(event_path)
    record = logging.LogRecord("model", logging.INFO, __file__, 1, "model_call", (), None)
    record.model_event = {
        "event": "model_call",
        "request_id": "release-smoke-request",
        "outcome": "success",
    }

    collector.emit(record)
    collector.close()

    lines = event_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == record.model_event


def test_model_smoke_blocks_fallback_even_when_provider_recovers():
    report = model_smoke._build_report(
        [
            {
                "name": "text_generation_and_constraints",
                "provider": "openai-compatible",
                "model": "fallback-model",
                "outcome": "passed",
            }
        ],
        [
            {
                "outcome": "failure",
                "fallback_from": None,
                "error_kind": "provider_5xx",
                "phase": "provider",
            },
            {
                "outcome": "success",
                "fallback_from": "primary-model",
                "error_kind": None,
                "phase": "provider",
            },
        ],
        "2026-09-06T00:00:00Z",
    )

    assert report["status"] == "failed"
    assert report["errors"] == ["fallback_requires_manual_confirmation"]


def test_deployment_requires_model_smoke_and_workflow_is_protected():
    root = Path(__file__).resolve().parents[1]
    deploy = (root / ".github/workflows/deploy-production.yml").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/model-smoke.yml").read_text(encoding="utf-8")
    test_script = (root / "test.sh").read_text(encoding="utf-8")

    assert "const requiredWorkflows = [" in deploy
    assert "'Model Smoke'" in deploy
    assert "workflow_id: 'model-smoke.yml'" in deploy
    assert "environment:\n      name: model-smoke" in workflow
    assert "MODEL_SMOKE_ENABLED: \"1\"" in workflow
    assert "E2E_DETERMINISTIC_STORY: \"0\"" in workflow
    assert "model-smoke)" in test_script
