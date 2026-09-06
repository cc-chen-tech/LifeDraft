"""Usage telemetry contracts for story-generation provider calls."""

import logging
from contextlib import contextmanager
from types import SimpleNamespace

import openai
import pytest

from src.ai.client import AIClient
from src.observability.request_context import RequestContext, request_context
pytestmark = [pytest.mark.unit]


@contextmanager
def _capture_model_events(caplog):
    """Capture the dedicated non-propagating model logger in isolation."""
    logger = logging.getLogger("model")
    previous_propagate = logger.propagate
    logger.propagate = False
    logger.addHandler(caplog.handler)
    try:
        yield
    finally:
        logger.removeHandler(caplog.handler)
        logger.propagate = previous_propagate


def _response(content: str = "ok"):
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=30,
            total_tokens=150,
            prompt_cache_hit_tokens=100,
            prompt_cache_miss_tokens=20,
        ),
    )


def test_non_streaming_call_reports_cache_usage_without_prompt_content():
    def create(**_kwargs):
        return _response()

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client = AIClient(api_key="test", model="deepseek-v4-flash")
    client.client = fake_client
    usage = []

    assert client.call("system", "secret story", usage_callback=usage.append) == "ok"

    assert usage[0].model == "deepseek-v4-flash"
    assert usage[0].prompt_cache_hit_tokens == 100
    assert usage[0].prompt_cache_miss_tokens == 20
    assert not hasattr(usage[0], "prompt")


def test_streaming_v4_request_includes_usage_and_reports_terminal_usage():
    terminal = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=None), finish_reason="stop")],
        usage=SimpleNamespace(
            prompt_tokens=50,
            completion_tokens=10,
            total_tokens=60,
            prompt_cache_hit_tokens=45,
            prompt_cache_miss_tokens=5,
        ),
    )
    chunks = [
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"), finish_reason=None)],
            usage=None,
        ),
        terminal,
    ]
    captured_kwargs = {}

    def create(**kwargs):
        captured_kwargs.update(kwargs)
        return iter(chunks)

    client = AIClient(api_key="test", model="deepseek-v4-pro")
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    usage = []

    assert client.call("system", "secret story", stream_callback=lambda _text: None, usage_callback=usage.append) == "hello"

    assert captured_kwargs["stream_options"] == {"include_usage": True}
    assert usage[0].streamed is True
    assert usage[0].prompt_cache_hit_tokens == 45


def test_raw_stream_emits_one_terminal_success_event(caplog):
    chunks = [
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"), finish_reason=None)],
            usage=None,
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=None), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=4, completion_tokens=1, total_tokens=5),
        ),
    ]
    client = AIClient(api_key="test", model="deepseek-v4-flash")
    client.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_kwargs: iter(chunks)))
    )

    with _capture_model_events(caplog), request_context(
        RequestContext(request_id="req-stream-1", operation_id="op-stream-1")
    ), caplog.at_level(logging.INFO, logger="model"):
        assert [chunk.choices[0].delta.content for chunk in client.stream("system", "story")] == [
            "hello",
            None,
        ]

    events = [record.model_event for record in caplog.records if hasattr(record, "model_event")]
    assert len(events) == 1
    assert events[0]["outcome"] == "success"
    assert events[0]["streamed"] is True
    assert events[0]["output_size"] == 5
    assert events[0]["total_tokens"] == 5
    assert events[0]["request_id"] == "req-stream-1"


def test_ai_client_emits_correlated_success_event_without_prompt_content(caplog, monkeypatch):
    monkeypatch.setenv("ENABLE_MODEL_FALLBACK", "false")
    client = AIClient(api_key="test", model="deepseek-v4-flash")
    client.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kwargs: _response("safe output"))
        )
    )

    with _capture_model_events(caplog), request_context(
        RequestContext(
            request_id="req-ai-1",
            operation_id="op-ai-1",
            feature="story_generation",
            operation="continuation",
        )
    ), caplog.at_level(logging.INFO, logger="model"):
        assert client.call("private system", "private story") == "safe output"

    events = [record.model_event for record in caplog.records if hasattr(record, "model_event")]
    assert len(events) == 1
    assert events[0]["request_id"] == "req-ai-1"
    assert events[0]["operation_id"] == "op-ai-1"
    assert events[0]["feature"] == "story_generation"
    assert events[0]["operation"] == "continuation"
    assert events[0]["model"] == "deepseek-v4-flash"
    assert events[0]["outcome"] == "success"
    assert events[0]["total_tokens"] == 150
    assert "private story" not in str(events[0])


def test_ai_client_emits_terminal_failure_event_for_provider_error(caplog, monkeypatch):
    monkeypatch.setenv("ENABLE_MODEL_FALLBACK", "false")
    error = openai.APIError(
        "Authorization: Bearer sk-secret; private story",
        request=None,
        body=None,
    )
    error.status_code = 429

    def create(**_kwargs):
        raise error

    client = AIClient(api_key="test", model="deepseek-v4-flash")
    client.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    with _capture_model_events(caplog), request_context(
        RequestContext(request_id="req-ai-2")
    ), caplog.at_level(logging.INFO, logger="model"):
        with pytest.raises(openai.APIError):
            client.call("system", "private story")

    events = [record.model_event for record in caplog.records if hasattr(record, "model_event")]
    assert len(events) == 1
    assert events[0]["outcome"] == "failure"
    assert events[0]["error_kind"] == "rate_limit"
    assert events[0]["http_status"] == 429
    assert "sk-secret" not in events[0]["error_message"]
    assert "private story" not in str(events[0])


def test_outer_retry_index_is_preserved_in_terminal_events(caplog, monkeypatch):
    monkeypatch.setenv("ENABLE_MODEL_FALLBACK", "false")
    retry_error = openai.APIError("temporary provider failure", request=None, body=None)
    responses = iter([retry_error, _response("recovered")])

    def create(**_kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    client = AIClient(api_key="test", model="deepseek-v4-flash")
    client.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    with _capture_model_events(caplog), request_context(
        RequestContext(request_id="req-retry-1", operation_id="op-retry-1")
    ), caplog.at_level(logging.INFO, logger="model"):
        assert client.call_with_retry("system", "private story", retry_count=2) == "recovered"

    events = [record.model_event for record in caplog.records if hasattr(record, "model_event")]
    assert [event["outcome"] for event in events] == ["failure", "success"]
    assert [event["retry_index"] for event in events] == [0, 1]
    assert [event["attempt"] for event in events] == [1, 2]


def test_call_json_emits_validation_failure_without_model_payload(caplog, monkeypatch):
    monkeypatch.setenv("ENABLE_MODEL_FALLBACK", "false")
    client = AIClient(api_key="test", model="deepseek-v4-flash")
    client.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kwargs: _response("not json"))
        )
    )

    with _capture_model_events(caplog), request_context(
        RequestContext(request_id="req-json-1", operation_id="op-json-1")
    ), caplog.at_level(logging.INFO, logger="model"):
        assert client.call_json("private system", "private story") is None

    events = [record.model_event for record in caplog.records if hasattr(record, "model_event")]
    assert [event["outcome"] for event in events] == ["success", "failure"]
    assert events[-1]["phase"] == "validation"
    assert events[-1]["operation"] == "json_parse"
    assert events[-1]["error_kind"] == "invalid_output"
    assert events[-1]["request_id"] == "req-json-1"
    assert "private story" not in str(events)
