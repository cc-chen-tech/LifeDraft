"""Production formatting must preserve causality without private payloads."""

import io
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from config.logging_config import JsonLogFormatter
from src.observability.model_telemetry import ModelCallContext, emit_model_call, configure_model_logging


def test_freeform_failure_keeps_site_and_identity_without_error_text():
    from src.observability.diagnostics import diagnostic_context

    with diagnostic_context(user_id=7, game_id=31, operation_id="story:31"):
        try:
            raise ValueError("private story sk-live-secret")
        except ValueError:
            record = logging.LogRecord("src.services.example", logging.ERROR, __file__, 21,
                                       "failed private story", (), __import__('sys').exc_info())
            payload = json.loads(JsonLogFormatter().format(record))
    assert payload["user_id"] == 7
    assert payload["game_id"] == 31
    assert payload["operation_id"] == "story:31"
    assert payload["exception_type"] == "ValueError"
    assert payload["exception_frames"][-1]["function"] == "test_freeform_failure_keeps_site_and_identity_without_error_text"
    assert payload["source_line"] == 21
    assert "private story" not in json.dumps(payload)
    assert "sk-live" not in json.dumps(payload)


def test_two_users_task_contexts_are_isolated_and_private_fields_dropped():
    from src.observability.diagnostics import diagnostic_context, emit_diagnostic
    from src.observability.request_context import current_request_context

    def run(user):
        with diagnostic_context(user_id=user, job_id=user * 10, job_type="voice",
                                operation_id=f"voice:{user * 10}"):
            with diagnostic_context(segment_index=2):
                return emit_diagnostic("voice_segment", phase="synthesis", outcome="failed",
                                       error_code="provider_timeout", story_text="PRIVATE", token="SECRET")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, [1, 2]))
    assert [(p["user_id"], p["job_id"], p["segment_index"]) for p in results] == [(1, 10, 2), (2, 20, 2)]
    assert "PRIVATE" not in json.dumps(results) and "SECRET" not in json.dumps(results)
    assert current_request_context() is None


def test_provider_business_code_survives_wrapper_and_inherits_task_context():
    from src.observability.diagnostics import diagnostic_context

    root = RuntimeError("private supplier payload")
    root.code = "2056"
    root.provider_trace_id = "trace-123"
    wrapped = RuntimeError("synthesis failed")
    wrapped.__cause__ = root
    with diagnostic_context(user_id=5, game_id=6, job_id=9, job_type="voice", segment_index=1):
        payload = emit_model_call(ModelCallContext("req", "voice:9", "tts", "scene", "provider", "minimax", "speech"),
                                  "failure", time.monotonic(), error=wrapped)
    assert payload["provider_code"] == "2056"
    assert payload["provider_trace_id"] == "trace-123"
    assert (payload["user_id"], payload["job_id"], payload["segment_index"]) == (5, 9, 1)
    assert "private supplier" not in json.dumps(payload)


def test_model_events_are_retained_in_rotating_file_without_duplicate_writes(tmp_path):
    from logging.handlers import RotatingFileHandler
    path = tmp_path / "model.jsonl"
    logger = configure_model_logging(stream=io.StringIO(), log_file=path)
    configure_model_logging(log_file=path)
    try:
        emit_model_call(ModelCallContext("req", "op", "tts", "scene", "provider", "local", "fixture"),
                        "success", time.monotonic())
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows) == 1 and rows[0]["request_id"] == "req"
        handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(handlers) == 1 and handlers[0].maxBytes > 0 and handlers[0].backupCount > 0
    finally:
        for handler in logger.handlers[:]:
            if isinstance(handler, RotatingFileHandler):
                logger.removeHandler(handler)
                handler.close()


def test_wrapped_provider_failures_keep_root_category_and_response_status():
    from types import SimpleNamespace
    from src.observability.model_telemetry import classify_model_error
    for root, expected, status in [(TimeoutError('private'), 'timeout', None),
                                   (RuntimeError('private'), 'rate_limit', 429),
                                   (RuntimeError('private'), 'provider_5xx', 503)]:
        if status:
            root.response = SimpleNamespace(status_code=status)
        wrapped = RuntimeError('private wrapper')
        wrapped.__cause__ = root
        payload = emit_model_call(ModelCallContext('req', 'op', 'tts', 'scene', 'provider', 'local', 'fixture'),
                                  'failure', time.monotonic(), error=wrapped)
        assert classify_model_error(wrapped) == expected
        assert payload['http_status'] == status
