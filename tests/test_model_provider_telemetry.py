"""Provider-boundary telemetry contracts for image and speech calls."""

import base64
from pathlib import Path

import pytest

from src.ai.image_exceptions import ImageProviderError
from src.ai.image_generator import ImageGenerator
from src.observability.model_telemetry import classify_model_error
from src.observability.request_context import RequestContext, request_context
from src.services.minimax_config import MiniMaxConfig
from src.services.minimax_story_tts_provider import MiniMaxTTSProvider

pytestmark = [pytest.mark.unit]


def _image_payload() -> dict[str, object]:
    return {
        "data": {
            "image_base64": [
                base64.b64encode(b"png-bytes").decode("ascii"),
            ]
        }
    }


def test_image_attempt_emits_only_safe_terminal_success_event(monkeypatch):
    events = []
    monkeypatch.setattr(
        "src.ai.image_generator.emit_model_call",
        lambda context, outcome, started_at, **kwargs: events.append(
            {"context": context, "outcome": outcome, **kwargs}
        ),
    )
    generator = ImageGenerator(
        api_key="configured",
        base_url="https://images.example/v1",
        model="image-01",
    )
    generator.max_retries = 1
    generator.text_to_image_models = ["image-01"]
    generator._call_api = lambda **_kwargs: _image_payload()  # type: ignore[method-assign]

    with request_context(
        RequestContext(
            request_id="req-image-1",
            operation_id="op-image-1",
            feature="story_generation",
        )
    ):
        image_bytes, _ = generator.generate_image("private image prompt")

    assert image_bytes == b"png-bytes"
    assert len(events) == 1
    event = events[0]
    assert event["outcome"] == "success"
    assert event["context"].request_id == "req-image-1"
    assert event["context"].operation_id == "op-image-1"
    assert event["context"].provider == "minimax"
    assert event["context"].operation == "image_generation"
    assert event["output_size"] == len(image_bytes)
    assert "private image prompt" not in str(event)


def test_image_fallback_emits_one_event_per_attempt_with_fallback_metadata(monkeypatch):
    events = []
    monkeypatch.setattr(
        "src.ai.image_generator.emit_model_call",
        lambda context, outcome, started_at, **kwargs: events.append(
            {"context": context, "outcome": outcome, **kwargs}
        ),
    )
    monkeypatch.setattr("src.ai.image_generator.time.sleep", lambda _seconds: None)
    generator = ImageGenerator(
        api_key="configured",
        base_url="https://images.example/v1",
        model="image-01",
    )
    generator.max_retries = 1
    generator.text_to_image_models = ["primary", "fallback"]
    responses = iter(
        [
            ImageProviderError(
                code="rate_limited",
                category="rate_limit",
                retryable=True,
                public_message="temporarily unavailable",
            ),
            _image_payload(),
        ]
    )

    def call_api(**_kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    generator._call_api = call_api  # type: ignore[method-assign]
    generator.generate_image("private fallback image prompt")

    assert len(events) == 2
    assert events[0]["outcome"] == "failure"
    assert events[0]["context"].retry_index == 0
    assert events[1]["outcome"] == "success"
    assert events[1]["context"].fallback_from == "primary"
    assert events[1]["context"].attempt == 2


def test_tts_attempt_event_is_emitted_after_audio_is_published(tmp_path: Path, monkeypatch):
    events = []
    monkeypatch.setattr(
        "src.services.minimax_story_tts_provider.emit_model_call",
        lambda context, outcome, started_at, **kwargs: events.append(
            {"context": context, "outcome": outcome, **kwargs}
        ),
    )
    monkeypatch.setattr(
        "src.services.minimax_story_tts_provider._validated_audio_duration_ms",
        lambda _path, _extension: 120,
    )

    class FakeClient:
        def synthesize_to_file(self, payload, output_path, on_progress=None):
            output_path.write_bytes(b"valid-audio")
            return None

    config = MiniMaxConfig.from_env(
        env={"MINIMAX_API_KEY": "configured"},
        voice_asset_dir=tmp_path / "voice",
    )
    provider = MiniMaxTTSProvider(config=config, client=FakeClient())  # type: ignore[arg-type]

    with request_context(
        RequestContext(
            request_id="req-tts-1",
            operation_id="op-tts-1",
            feature="story_reading",
        )
    ):
        speech = provider.synthesize(
            {"text_hash": "tts-smoke", "text": "private story"},
            "warm_female",
            1.0,
        )

    assert speech.duration_ms == 120
    assert len(events) == 1
    event = events[0]
    assert event["outcome"] == "success"
    assert event["context"].request_id == "req-tts-1"
    assert event["context"].operation_id == "op-tts-1"
    assert event["context"].operation == "tts_synthesis"
    assert event["output_size"] == len(b"valid-audio")
    assert "private story" not in str(event)


def test_tts_invalid_audio_emits_invalid_output_failure(tmp_path: Path, monkeypatch):
    events = []
    monkeypatch.setattr(
        "src.services.minimax_story_tts_provider.emit_model_call",
        lambda context, outcome, started_at, **kwargs: events.append(
            {"context": context, "outcome": outcome, **kwargs}
        ),
    )

    class InvalidClient:
        def synthesize_to_file(self, payload, output_path, on_progress=None):
            output_path.write_bytes(b"not-audio")
            return None

    config = MiniMaxConfig.from_env(
        env={"MINIMAX_API_KEY": "configured"},
        voice_asset_dir=tmp_path / "voice",
    )
    provider = MiniMaxTTSProvider(config=config, client=InvalidClient())  # type: ignore[arg-type]

    from src.services.story_tts_provider import TTSProviderUnavailableError

    with pytest.raises(TTSProviderUnavailableError):
        provider.synthesize(
            {"text_hash": "invalid-tts", "text": "private story"},
            "warm_female",
            1.0,
        )

    assert len(events) == 1
    assert events[0]["outcome"] == "failure"
    assert events[0]["context"].operation == "tts_synthesis"
    assert classify_model_error(events[0]["error"]) == "invalid_output"
