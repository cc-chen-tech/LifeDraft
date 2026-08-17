"""Provider-boundary contracts for image generation failures."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from src.ai.image_exceptions import ImageProviderError
from src.ai.image_generator import ImageGenerator

pytestmark = [pytest.mark.unit]



class FakeResponse:
    text = ""

    def __init__(self, payload: dict[str, Any], *, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload


class CountingSession:
    def __init__(self, payload: dict[str, Any], *, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.post_calls = 0

    def post(self, *args: Any, **kwargs: Any) -> FakeResponse:
        self.post_calls += 1
        return FakeResponse(self.payload, status_code=self.status_code)


class TimeoutSession:
    def post(self, *args: Any, **kwargs: Any) -> FakeResponse:
        raise requests.Timeout("provider timed out")


def configured_generator(
    payload: dict[str, Any],
    *,
    max_retries: int = 3,
    models: tuple[str, ...] = ("image-01", "image-01-live"),
) -> tuple[ImageGenerator, CountingSession]:
    generator = ImageGenerator(
        api_key="test-key",
        base_url="https://example.invalid/v1",
    )
    session = CountingSession(payload)
    generator.session = session
    generator.max_retries = max_retries
    generator.text_to_image_models = list(models)
    return generator, session


def test_minimax_2056_is_typed_capacity_failure_and_is_not_retried(monkeypatch):
    monkeypatch.setattr("src.ai.image_generator.time.sleep", lambda _seconds: None)
    generator, session = configured_generator(
        {"base_resp": {"status_code": 2056, "status_msg": "limit"}}
    )

    with pytest.raises(ImageProviderError) as raised:
        generator.generate_image("safe diagnostic prompt")

    assert raised.value.code == "minimax_2056"
    assert raised.value.category == "capacity"
    assert raised.value.retryable is False
    assert raised.value.public_message == "图片生成额度暂时不可用，请稍后再试"
    assert session.post_calls == 1


def test_missing_image_provider_config_is_typed_and_safe():
    generator = ImageGenerator(
        api_key="test-key",
        base_url="https://example.invalid/v1",
    )
    generator.api_key = None
    generator.base_url = None

    with pytest.raises(ImageProviderError) as raised:
        generator._call_api(prompt="safe", model="image-01")

    assert raised.value.code == "image_provider_not_configured"
    assert raised.value.category == "configuration"
    assert raised.value.retryable is False
    assert "API key" not in raised.value.public_message


def test_minimax_transient_upstream_failure_remains_bounded(monkeypatch):
    monkeypatch.setattr("src.ai.image_generator.time.sleep", lambda _seconds: None)
    generator, session = configured_generator(
        {"base_resp": {"status_code": 1033, "status_msg": "upstream"}},
        max_retries=2,
        models=("image-01",),
    )

    with pytest.raises(ImageProviderError) as raised:
        generator.generate_image("safe diagnostic prompt")

    assert raised.value.category == "upstream"
    assert raised.value.retryable is True
    assert session.post_calls == 2


def test_valid_minimax_business_response_is_returned():
    payload = {
        "data": {"image_urls": ["https://example.invalid/image.png"]},
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }
    generator, session = configured_generator(payload)

    assert generator._call_api(prompt="safe", model="image-01") == payload
    assert session.post_calls == 1


def test_provider_timeout_is_typed_and_retryable():
    generator = ImageGenerator(
        api_key="test-key",
        base_url="https://example.invalid/v1",
    )
    generator.session = TimeoutSession()

    with pytest.raises(ImageProviderError) as raised:
        generator._call_api(prompt="safe", model="image-01")

    assert raised.value.category == "timeout"
    assert raised.value.retryable is True


def test_success_status_without_image_output_is_invalid_response(monkeypatch):
    monkeypatch.setattr("src.ai.image_generator.time.sleep", lambda _seconds: None)
    generator, session = configured_generator(
        {"base_resp": {"status_code": 0}},
        max_retries=1,
        models=("image-01",),
    )

    with pytest.raises(ImageProviderError) as raised:
        generator.generate_image("safe")

    assert raised.value.category == "invalid_response"
    assert raised.value.retryable is False
    assert session.post_calls == 1


@pytest.mark.parametrize(
    ("status_code", "category", "retryable"),
    [
        (401, "authentication", False),
        (429, "rate_limit", True),
        (503, "upstream", True),
    ],
)
def test_http_failures_are_classified_without_exposing_response_text(
    status_code: int,
    category: str,
    retryable: bool,
):
    generator, _ = configured_generator({})
    generator.session = CountingSession(
        {"secret": "provider internals"},
        status_code=status_code,
    )

    with pytest.raises(ImageProviderError) as raised:
        generator._call_api(prompt="safe", model="image-01")

    assert raised.value.category == category
    assert raised.value.retryable is retryable
    assert "provider internals" not in raised.value.public_message


def test_permanent_edit_failure_stops_character_variant_loop(monkeypatch):
    monkeypatch.setattr("src.ai.image_generator.time.sleep", lambda _seconds: None)
    generator, session = configured_generator(
        {"base_resp": {"status_code": 2056, "status_msg": "limit"}}
    )
    generator.image_edit_models = ["image-01"]

    with pytest.raises(ImageProviderError) as raised:
        generator.generate_character_images(
            name="test",
            description="test",
            reference_image_url="https://example.invalid/reference.png",
            num_images=3,
        )

    assert raised.value.code == "minimax_2056"
    assert session.post_calls == 1
