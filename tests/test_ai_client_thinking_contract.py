"""Request-shape contracts for opt-in DeepSeek V4 thinking control."""

import json
from collections.abc import Callable, Iterator
from typing import Any, Dict, Optional

import httpx
import openai
import pytest

from config.feature_flags import reset_features, set_feature
from src.ai.budgets import GenerationCallTracker, resolve_narrative_budget
from src.ai.client import AIClient
from src.ai.generator import EventGenerator

pytestmark = [pytest.mark.unit]


STREAM_RESPONSE = (
    'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":0,'
    '"model":"deepseek-v4-flash","choices":[{"index":0,"delta":{"role":"assistant",'
    '"content":"story"},"finish_reason":null}]}\n\n'
    'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":0,'
    '"model":"deepseek-v4-flash","choices":[{"index":0,"delta":{},'
    '"finish_reason":"stop"}]}\n\n'
    "data: [DONE]\n\n"
)

STREAM_LENGTH_RESPONSE = (
    'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":0,'
    '"model":"deepseek-v4-flash","choices":[{"index":0,"delta":{"role":"assistant",'
    '"content":"partial "},"finish_reason":null}]}\n\n'
    'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":0,'
    '"model":"deepseek-v4-flash","choices":[{"index":0,"delta":{},'
    '"finish_reason":"length"}]}\n\n'
    "data: [DONE]\n\n"
)


@pytest.fixture(autouse=True)
def _reset_feature_flags() -> Iterator[None]:
    reset_features()
    yield
    reset_features()


def _completion_response(
    request: httpx.Request,
    body: dict[str, Any],
    *,
    content: str = "story",
    finish_reason: str = "stop",
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": body["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        },
        request=request,
    )


def _capture_transport(seen: list[dict[str, Any]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if body.get("stream"):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=STREAM_RESPONSE,
                request=request,
            )
        return _completion_response(request, body)

    return httpx.MockTransport(handler)


def _ai_client(model: str, http_client: httpx.Client) -> AIClient:
    client = object.__new__(AIClient)
    client.api_key = "test-key"
    client.model = model
    client.client = openai.OpenAI(
        api_key="test-key",
        base_url="https://provider.test/v1",
        http_client=http_client,
        max_retries=0,
    )
    return client


@pytest.mark.parametrize("model", ["deepseek-v4-flash", "DeepSeek-V4-Pro"])
@pytest.mark.parametrize("streaming", [False, True])
def test_deepseek_v4_false_serializes_disabled_thinking(
    model: str,
    streaming: bool,
) -> None:
    seen: list[dict[str, Any]] = []
    chunks: list[str] = []
    with httpx.Client(transport=_capture_transport(seen)) as http_client:
        client = _ai_client(model, http_client)
        callback: Optional[Callable[[str], None]] = chunks.append if streaming else None
        result = client.call(
            "system",
            "user",
            max_tokens=4096,
            stream_callback=callback,
            thinking=False,
        )

    assert result == "story"
    assert len(seen) == 1
    assert seen[0]["max_tokens"] == 4096
    assert seen[0]["thinking"] == {"type": "disabled"}
    if streaming:
        assert chunks == ["story"]


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("thinking_kwargs", [{}, {"thinking": None}, {"thinking": True}])
def test_non_false_thinking_preserves_deepseek_payload(
    thinking_kwargs: Dict[str, Optional[bool]],
    streaming: bool,
) -> None:
    seen: list[dict[str, Any]] = []
    chunks: list[str] = []
    with httpx.Client(transport=_capture_transport(seen)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        callback: Optional[Callable[[str], None]] = chunks.append if streaming else None
        assert (
            client.call(
                "system",
                "user",
                stream_callback=callback,
                **thinking_kwargs,
            )
            == "story"
        )

    assert "thinking" not in seen[0]
    if streaming:
        assert chunks == ["story"]


@pytest.mark.parametrize("model", ["gpt-4o-mini", "deepseek-v3"])
def test_non_deepseek_v4_ignores_false_thinking(model: str) -> None:
    seen: list[dict[str, Any]] = []
    with httpx.Client(transport=_capture_transport(seen)) as http_client:
        client = _ai_client(model, http_client)
        assert client.call("system", "user", thinking=False) == "story"

    assert "thinking" not in seen[0]


def test_model_fallback_preserves_disabled_thinking_for_each_deepseek_model() -> None:
    seen: list[dict[str, Any]] = []
    tracker = GenerationCallTracker(resolve_narrative_budget("round", "generate", "master", "zh"))
    tracker.consume("prose")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if len(seen) <= 2:
            return httpx.Response(
                503,
                json={
                    "error": {
                        "message": "temporary provider failure",
                        "type": "server_error",
                        "code": "server_error",
                    }
                },
                request=request,
            )
        return _completion_response(request, body)

    set_feature("model_fallback", True)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        assert (
            client.call(
                "system",
                "user",
                thinking=False,
                generation_tracker=tracker,
            )
            == "story"
        )

    assert [body["model"] for body in seen] == [
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "gpt-4o-mini",
    ]
    assert all(body["thinking"] == {"type": "disabled"} for body in seen[:2])
    assert "thinking" not in seen[2]
    assert tracker.prose_calls == 3


def test_truncation_recovery_preserves_disabled_thinking() -> None:
    seen: list[dict[str, Any]] = []
    completions = iter(
        [
            ("partial ", "length"),
            ("ending.", "stop"),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        content, finish_reason = next(completions)
        return _completion_response(
            request,
            body,
            content=content,
            finish_reason=finish_reason,
        )

    set_feature("truncation_recovery", True)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        result = client.call("system", "user", thinking=False)

    assert result == "partial ending."
    assert len(seen) == 2
    assert all(body["thinking"] == {"type": "disabled"} for body in seen)


def test_streaming_truncation_recovery_preserves_disabled_thinking() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if body.get("stream"):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=STREAM_LENGTH_RESPONSE,
                request=request,
            )
        return _completion_response(request, body, content="ending.")

    chunks: list[str] = []
    set_feature("truncation_recovery", True)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        result = client.call(
            "system",
            "user",
            stream_callback=chunks.append,
            thinking=False,
        )

    assert result == "partial ending."
    assert chunks == ["partial "]
    assert len(seen) == 2
    assert seen[0]["stream"] is True
    assert "stream" not in seen[1]
    assert all(body["thinking"] == {"type": "disabled"} for body in seen)


def test_call_json_preserves_disabled_thinking() -> None:
    """Removing call_json propagation must expose the provider-default payload."""
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return _completion_response(request, body, content='{"value": 1}')

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        result = client.call_json("system", "user", thinking=False)

    assert result == {"value": 1}
    assert seen == [
        {
            "messages": [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            "model": "deepseek-v4-flash",
            "max_tokens": 2000,
            "thinking": {"type": "disabled"},
            "temperature": 0.8,
        }
    ]


def test_call_with_retry_preserves_disabled_thinking_on_every_attempt() -> None:
    """A retry must not silently return to DeepSeek's default thinking policy."""
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if len(seen) == 1:
            return httpx.Response(
                503,
                json={
                    "error": {
                        "message": "temporary provider failure",
                        "type": "server_error",
                        "code": "server_error",
                    }
                },
                request=request,
            )
        return _completion_response(request, body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        result = client.call_with_retry(
            "system",
            "user",
            retry_count=2,
            thinking=False,
        )

    assert result == "story"
    assert len(seen) == 2
    assert [body["thinking"] for body in seen] == [
        {"type": "disabled"},
        {"type": "disabled"},
    ]


def test_raw_generate_stream_serializes_disabled_thinking() -> None:
    """The raw opening-story stream must use the same request policy boundary."""
    seen: list[dict[str, Any]] = []
    with httpx.Client(transport=_capture_transport(seen)) as http_client:
        client = _ai_client("deepseek-v4-flash", http_client)
        generator = object.__new__(EventGenerator)
        generator.ai_client = client
        chunks = list(
            generator.generate_stream(
                prompt="user",
                system_prompt="system",
                thinking=False,
            )
        )

    assert len(chunks) == 2
    assert seen[0]["stream"] is True
    assert seen[0]["thinking"] == {"type": "disabled"}


@pytest.mark.parametrize(
    ("model", "thinking_kwargs"),
    [
        ("deepseek-v4-flash", {}),
        ("gpt-4o-mini", {"thinking": False}),
    ],
)
def test_raw_generate_stream_preserves_uncontrolled_payloads(
    model: str,
    thinking_kwargs: dict[str, bool],
) -> None:
    """Omitted controls and non-V4 models must retain their old payload shape."""
    seen: list[dict[str, Any]] = []
    with httpx.Client(transport=_capture_transport(seen)) as http_client:
        client = _ai_client(model, http_client)
        generator = object.__new__(EventGenerator)
        generator.ai_client = client
        list(generator.generate_stream("user", "system", **thinking_kwargs))

    assert "thinking" not in seen[0]
