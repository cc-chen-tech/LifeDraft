import io
import json
import logging

from config.logging_config import JsonLogFormatter


def test_request_id_is_returned_and_preserves_safe_inbound_value(client):
    response = client.get("/api/health", headers={"X-Request-ID": "release-smoke-1"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "release-smoke-1"
    assert len(response.headers["X-Operation-ID"]) == 32


def test_request_id_is_generated_for_invalid_or_missing_value(client):
    response = client.get("/api/health", headers={"X-Request-ID": "bad id"})

    request_id = response.headers["X-Request-ID"]
    assert response.status_code == 200
    assert len(request_id) == 32
    assert " " not in request_id


def test_json_log_formatter_keeps_extra_fields_machine_readable():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("request-observability-test")
    logger.handlers[:] = [handler]
    logger.propagate = False

    logger.info(
        "API Request",
        extra={
            "request_id": "req-1",
            "path": "/api/health",
            "status": 200,
            "duration_ms": 12.5,
        },
    )

    payload = json.loads(stream.getvalue())
    assert payload["message"] == "API Request"
    assert payload["request_id"] == "req-1"
    assert payload["path"] == "/api/health"
    assert payload["status"] == 200
    assert payload["duration_ms"] == 12.5


def test_production_formatter_suppresses_model_payloads_and_sensitive_extras():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("src.api.routers.images")
    logger.handlers[:] = [handler]
    logger.propagate = False

    logger.error(
        "provider response contains private story and sk-live-secret",
        extra={"prompt": "private story", "request_id": "req-2"},
    )

    payload = json.loads(stream.getvalue())
    assert payload["message"] == "model_subsystem_log_suppressed"
    assert payload["message_suppressed"] is True
    assert payload["request_id"] == "req-2"
    assert "private story" not in stream.getvalue()
    assert "sk-live-secret" not in stream.getvalue()
    assert "prompt" not in payload


def test_production_formatter_suppresses_gameplay_story_payloads():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("src.game.round.event_generator")
    logger.handlers[:] = [handler]
    logger.propagate = False

    logger.warning("generated story: private user story and user prompt")

    payload = json.loads(stream.getvalue())
    assert payload["message"] == "model_subsystem_log_suppressed"
    assert "private user story" not in stream.getvalue()
