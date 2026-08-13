"""Provider-free contracts for deterministic MiniMax image handling."""

import base64

import pytest

from src.ai.image_exceptions import ContentInspectionError, ImageProviderError
from src.ai.image_generator import ImageGenerator


def _generator(base_url: str = "https://images.example/v1") -> ImageGenerator:
    return ImageGenerator(api_key="test-key", base_url=base_url, model="image-01")


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://images.example", "https://images.example/v1/image_generation"),
        ("https://images.example/v1", "https://images.example/v1/image_generation"),
        (
            "https://images.example/v1/image_generation",
            "https://images.example/v1/image_generation",
        ),
    ],
)
def test_minimax_endpoint_normalizes_supported_base_urls(
    base_url: str, expected: str
) -> None:
    assert _generator(base_url)._image_generation_url() == expected


def test_payload_normalizes_prompt_count_format_size_and_references() -> None:
    payload = _generator()._build_minimax_payload(
        prompt="A quiet library",
        size="1664x928",
        n=99,
        response_format="unsupported",
        model="image-01",
        extra_params={
            "response_format": "base64",
            "negative_prompt": "blurred",
            "seed": 7,
            "style": "cinematic",
            "prompt_optimizer": False,
        },
        subject_reference=[{"type": "character", "image_file": "data:image/png;base64,AA=="}],
    )

    assert payload == {
        "model": "image-01",
        "prompt": "A quiet library\nAvoid: blurred",
        "response_format": "base64",
        "n": 9,
        "prompt_optimizer": False,
        "aspect_ratio": "16:9",
        "subject_reference": [
            {"type": "character", "image_file": "data:image/png;base64,AA=="}
        ],
        "seed": 7,
        "style": "cinematic",
    }


def test_payload_uses_safe_fallback_for_invalid_size_and_bounded_prompt() -> None:
    payload = _generator()._build_minimax_payload(
        prompt="a" * 1490,
        size="not-a-size",
        n=0,
        response_format="url",
        model="image-01-live",
        extra_params={"negative_prompt": "blocked" * 20},
    )

    assert payload["aspect_ratio"] == "1:1"
    assert payload["n"] == 1
    assert payload["response_format"] == "url"
    assert len(payload["prompt"]) == 1500
    assert payload["prompt"].startswith("a" * 1490 + "\nAvoid: bl")


def test_payload_explicit_dimension_override_replaces_derived_aspect_ratio() -> None:
    payload = _generator()._build_minimax_payload(
        prompt="portrait",
        size="928*1664",
        n=1,
        response_format="url",
        model="image-01",
        extra_params={"width": 1024, "height": 1536},
    )

    assert payload["width"] == 1024
    assert payload["height"] == 1536
    assert "aspect_ratio" not in payload


def test_image_sources_and_base64_data_are_normalized() -> None:
    generator = _generator()
    kind, urls = generator._minimax_image_sources(
        {"data": {"image_urls": ["", "https://images.example/result.png"]}}
    )
    encoded = base64.b64encode(b"image-bytes").decode("ascii")
    base64_kind, encoded_images = generator._minimax_image_sources(
        {"data": {"image_base64": [encoded]}}
    )

    assert (kind, urls) == ("url", ["https://images.example/result.png"])
    assert (base64_kind, encoded_images) == ("base64", [encoded])
    assert generator._decode_base64_image(f"data:image/png;base64,{encoded}") == b"image-bytes"


@pytest.mark.parametrize(
    "result",
    [{}, {"data": {}}, {"data": {"image_urls": ["", None]}}],
)
def test_missing_image_sources_are_safe_invalid_responses(result: dict) -> None:
    with pytest.raises(ImageProviderError) as raised:
        _generator()._minimax_image_sources(result)

    assert raised.value.code == "image_provider_invalid_response"
    assert raised.value.category == "invalid_response"
    assert raised.value.retryable is False


def test_invalid_base64_is_a_safe_invalid_response() -> None:
    with pytest.raises(ImageProviderError) as raised:
        _generator()._decode_base64_image("not valid base64!")

    assert raised.value.code == "image_provider_invalid_response"
    assert raised.value.category == "invalid_response"
    assert raised.value.retryable is False


@pytest.mark.parametrize(
    ("status_code", "category", "retryable"),
    [(401, "authentication", False), (429, "rate_limit", True), (503, "upstream", True)],
)
def test_http_statuses_have_typed_safe_provider_errors(
    status_code: int, category: str, retryable: bool
) -> None:
    error = _generator()._provider_error_for_http(status_code, operation="generate")

    assert error.code == f"image_provider_http_{status_code}_generate"
    assert error.category == category
    assert error.retryable is retryable


def test_minimax_capacity_and_content_safety_errors_keep_typed_semantics() -> None:
    generator = _generator()

    with pytest.raises(ImageProviderError) as capacity:
        generator._raise_for_minimax_error(
            {"base_resp": {"status_code": 2056, "status_msg": "quota"}, "trace_id": "trace-1"},
            prompt="safe prompt",
        )
    with pytest.raises(ContentInspectionError):
        generator._raise_for_minimax_error(
            {"base_resp": {"status_code": 1026, "status_msg": "blocked"}},
            prompt="safe prompt",
        )

    assert capacity.value.code == "minimax_2056"
    assert capacity.value.category == "capacity"
    assert capacity.value.retryable is False
    assert capacity.value.provider_trace_id == "trace-1"
