"""Usage telemetry contracts for story-generation provider calls."""

from types import SimpleNamespace

from src.ai.client import AIClient
import pytest

pytestmark = [pytest.mark.unit]



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
    create = lambda **_kwargs: _response()
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
