from types import SimpleNamespace

from src.observability.request_context import (
    RequestContext,
    bind_current_context,
    current_request_context,
    request_context,
    resolve_request_id,
)
from src.ai.generator import EventGenerator


def test_resolve_request_id_preserves_safe_client_id():
    assert resolve_request_id("release-check-123") == "release-check-123"


def test_resolve_request_id_rejects_unsafe_or_oversized_values():
    generated = resolve_request_id("bad id with spaces")
    assert generated != "bad id with spaces"
    assert len(generated) == 32

    generated = resolve_request_id("x" * 129)
    assert len(generated) == 32


def test_request_context_is_scoped_and_restored():
    assert current_request_context() is None


def test_bound_callable_carries_operation_context_to_worker():
    with request_context(
        RequestContext(request_id="req-worker", operation_id="op-worker")
    ):
        bound = bind_current_context(current_request_context)
        worker_context = bound()

    assert worker_context is not None
    assert worker_context.request_id == "req-worker"
    assert worker_context.operation_id == "op-worker"

    with request_context(RequestContext(request_id="req-1", operation_id="op-1")):
        assert current_request_context() == RequestContext(
            request_id="req-1", operation_id="op-1"
        )

    assert current_request_context() is None


def test_round_generation_overrides_context_with_explicit_operation_id():
    captured = {}
    generator = EventGenerator.__new__(EventGenerator)
    generator.option_gen = object()

    def fake_generate_round_event(**_kwargs):
        captured["context"] = current_request_context()
        return object()

    generator.story_gen = SimpleNamespace(generate_round_event=fake_generate_round_event)

    with request_context(RequestContext(request_id="req-parent", operation_id="op-parent")):
        generator.generate_round_event(
            player_state={},
            language="en",
            round_number=0,
            round_context="",
            operation_id="op-child",
        )

    assert captured["context"].request_id == "req-parent"
    assert captured["context"].operation_id == "op-child"
    assert current_request_context() is None
