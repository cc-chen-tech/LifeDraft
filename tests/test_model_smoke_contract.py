import json
import logging
from pathlib import Path
from types import SimpleNamespace

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


def test_story_origin_smoke_checks_real_origin_validation_with_one_call():
    from src.observability.request_context import current_request_context

    collector = SimpleNamespace(events=[])

    class Provider:
        def generate_completion_json(self, **_kwargs):
            context = current_request_context()
            collector.events.append({
                "operation_id": context.operation_id,
                "phase": "provider",
                "outcome": "success",
                "finish_reason": "stop",
            })
            return {
                "start_date": "2026-08-13",
                "starting_age": 28,
                "era_description": "2020年代的上海",
                "life_stage_description": "28岁的职业阶段",
                "world_context": "上海的现代设计行业",
            }

    assert model_smoke._run_story_origin_check(Provider(), collector) == {
        "provider_calls": 1,
        "constraints_matched": True,
    }


def test_story_origin_smoke_rejects_hidden_second_provider_call():
    from src.observability.request_context import current_request_context

    collector = SimpleNamespace(events=[])

    class Provider:
        calls = 0

        def generate_completion_json(self, **_kwargs):
            self.calls += 1
            context = current_request_context()
            collector.events.append({
                "operation_id": context.operation_id,
                "phase": "provider",
                "outcome": "success",
                "finish_reason": "stop",
            })
            return {
                "start_date": "2026-08-13",
                "starting_age": 27 if self.calls == 1 else 28,
                "era_description": "2020年代的上海",
                "life_stage_description": "设计师的职业阶段",
                "world_context": "上海的现代设计行业",
            }

    provider = Provider()
    with pytest.raises(RuntimeError, match="story_origin_repeated_provider_call"):
        model_smoke._run_story_origin_check(provider, collector)
    assert provider.calls == 2


def test_story_origin_smoke_rejects_hidden_transport_retry():
    from src.observability.request_context import current_request_context

    collector = SimpleNamespace(events=[])

    class Provider:
        def generate_completion_json(self, **_kwargs):
            context = current_request_context()
            for _ in range(2):
                collector.events.append({
                    "operation_id": context.operation_id,
                    "phase": "provider",
                    "outcome": "success",
                    "finish_reason": "stop",
                })
            return {
                "start_date": "2026-08-13",
                "starting_age": 28,
                "era_description": "2020年代的上海",
                "life_stage_description": "设计师的职业阶段",
                "world_context": "上海的现代设计行业",
            }

    with pytest.raises(RuntimeError, match="story_origin_provider_attempts_invalid"):
        model_smoke._run_story_origin_check(Provider(), collector)


def test_story_origin_smoke_rejects_provider_token_limit():
    from src.observability.request_context import current_request_context

    collector = SimpleNamespace(events=[])

    class Provider:
        def generate_completion_json(self, **_kwargs):
            context = current_request_context()
            collector.events.append({
                "operation_id": context.operation_id,
                "phase": "provider",
                "outcome": "success",
                "finish_reason": "length",
            })
            return {
                "start_date": "2026-08-13",
                "starting_age": 28,
                "era_description": "2020年代的上海",
                "life_stage_description": "设计师的职业阶段",
                "world_context": "上海的现代设计行业",
            }

    with pytest.raises(RuntimeError, match="story_origin_provider_truncated"):
        model_smoke._run_story_origin_check(Provider(), collector)


def test_model_smoke_run_includes_story_origin_in_release_report(monkeypatch, tmp_path):
    from src.ai import generator as generator_module
    from src.ai import image_generator as image_module
    from src.services import minimax_story_tts_provider as tts_module

    fake_text_generator = SimpleNamespace(ai_client=SimpleNamespace(model="test-text"))
    monkeypatch.setattr(generator_module, "EventGenerator", lambda **_kwargs: fake_text_generator)
    monkeypatch.setattr(image_module, "ImageGenerator", lambda: SimpleNamespace(model="test-image"))
    monkeypatch.setattr(tts_module, "MiniMaxTTSProvider", lambda: SimpleNamespace(model="test-tts"))
    monkeypatch.setattr(model_smoke, "_require_real_credentials", lambda: None)
    monkeypatch.setattr(model_smoke, "_check_audio_runtime", lambda: None)
    monkeypatch.setattr(
        model_smoke, "_configure_safe_logging", lambda _path: SimpleNamespace(events=[])
    )
    for name in ("_run_text_checks", "_run_image_check", "_run_tts_check", "_run_projection_check", "_run_daily_opening_check"):
        monkeypatch.setattr(model_smoke, name, lambda *_args: {})
    origin_checks = []

    def origin_check(generator, _collector):
        origin_checks.append(generator)
        return {"provider_calls": 1, "constraints_matched": True}

    monkeypatch.setattr(model_smoke, "_run_story_origin_check", origin_check)
    report_path = tmp_path / "smoke-summary.json"
    assert model_smoke.run(report_path, tmp_path / "artifacts", None) == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    origin = next(
        check for check in report["checks"] if check["name"] == "story_origin_generation"
    )
    assert origin["outcome"] == "passed"
    assert origin["details"] == {"provider_calls": 1, "constraints_matched": True}
    assert origin_checks == [fake_text_generator]
    assert any(check["name"] == "daily_opening_delivery" and check["outcome"] == "passed" for check in report["checks"])


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


def test_successful_dispatched_model_smoke_explicitly_starts_candidate_deploy():
    root = Path(__file__).resolve().parents[1]
    deploy = (root / ".github/workflows/deploy-production.yml").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/model-smoke.yml").read_text(encoding="utf-8")

    assert "request-deploy:" in workflow
    assert "needs: model-smoke" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.deploy_after_success" in workflow
    assert "deploy_after_success: 'true'" in deploy
    assert "actions: write" in workflow
    assert "workflow_id: 'deploy-production.yml'" in workflow
    assert "candidate_sha: process.env.CANDIDATE_SHA" in workflow
    assert "candidate_sha:" in deploy
    assert "${{ inputs.candidate_sha }}" in deploy


def test_daily_release_smoke_uses_production_flags_without_credential_traces():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    workflow = (root / '.github/workflows/model-smoke.yml').read_text()
    runner = (root / 'test.sh').read_text()
    browser = (root / 'frontend/e2e/model-smoke.spec.ts').read_text()
    assert 'ENABLE_CONSTRAINT_HARNESS: "true"' in workflow
    assert 'ENABLE_SOFT_NARRATIVE_LENGTHS: "true"' in workflow
    assert 'ENABLE_UNIFIED_NARRATIVE_BUDGETS: "false"' in workflow
    assert 'e2e/model-smoke.spec.ts --project=core --workers=1 --trace=off' in runner
    assert 'trace.zip' not in workflow
    assert 'await expect(expand).toBeVisible()' in browser
