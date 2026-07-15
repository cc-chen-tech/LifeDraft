"""Provider-free transport contracts for typed image generation failures."""

from typing import Any

import pytest

from src.ai.image_exceptions import ContentInspectionError, ImageProviderError
from src.ai.image_generator import ImageGenerator


class _Response:
    def __init__(self, status_code: int, payload: object = None) -> None:
        self.status_code = status_code
        self.payload = payload
        self.content = b"provider-body"

    def json(self) -> object:
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class _Session:
    def __init__(self, post_response: _Response, get_response: _Response | None = None) -> None:
        self.post_response = post_response
        self.get_response = get_response or post_response

    def post(self, *_args: Any, **_kwargs: Any) -> _Response:
        return self.post_response

    def get(self, *_args: Any, **_kwargs: Any) -> _Response:
        return self.get_response


def _generator(session: _Session) -> ImageGenerator:
    generator = ImageGenerator(api_key="contract-key", base_url="https://images.example/v1")
    generator.session = session
    return generator


def test_edit_content_inspection_response_preserves_safe_prompt_context() -> None:
    generator = _generator(
        _Session(_Response(400, {"code": "DataInspectionFailed", "message": "policy detail"}))
    )

    with pytest.raises(ContentInspectionError) as raised:
        generator._call_edit_api(
            reference_image="data:image/png;base64,AA==",
            prompt="keep the person in a quiet library",
        )

    assert raised.value.original_prompt == "keep the person in a quiet library"
    assert raised.value.api_error_message == "DataInspectionFailed: policy detail"


def test_invalid_generation_json_becomes_typed_invalid_response() -> None:
    generator = _generator(_Session(_Response(200, ValueError("not json"))))

    with pytest.raises(ImageProviderError) as raised:
        generator._call_api(prompt="safe prompt", model="image-01")

    assert (raised.value.code, raised.value.category, raised.value.retryable) == (
        "image_provider_invalid_response",
        "invalid_response",
        False,
    )


def test_failed_download_uses_operation_specific_typed_error() -> None:
    generator = _generator(_Session(_Response(200, {}), _Response(503, {})))

    with pytest.raises(ImageProviderError) as raised:
        generator._download_image("https://images.example/failed.png")

    assert (raised.value.code, raised.value.category, raised.value.retryable) == (
        "image_provider_http_503_download",
        "upstream",
        True,
    )
