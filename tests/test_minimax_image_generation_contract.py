"""MiniMax image generation provider contract tests.

Layer 3: provider contract tests.
Target: text-to-image and image-to-image request/response compatibility.
Prevents: accidentally sending the old DashScope payload shape to MiniMax.
"""

from __future__ import annotations

import json
import threading
from contextlib import AbstractContextManager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

import pytest

from src.ai.image_exceptions import ContentInspectionError, ImageProviderError
from src.ai.image_generator import ImageGenerator

pytestmark = [pytest.mark.unit]



PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04"
    b"\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _MiniMaxCaptureHandler(BaseHTTPRequestHandler):
    requests_seen: ClassVar[list[dict[str, Any]]] = []
    image_response: ClassVar[dict[str, Any] | None] = None

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            body = {"_raw": raw_body.decode("utf-8", errors="replace")}

        self.requests_seen.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "content_type": self.headers.get("Content-Type"),
                "body": body,
            }
        )

        payload = self.image_response or {
            "id": "test-task",
            "data": {"image_urls": [f"http://127.0.0.1:{self.server.server_port}/image.png"]},
            "metadata": {"success_count": 1, "failed_count": 0},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }
        response_body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/image.png":
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(PNG_BYTES)))
        self.end_headers()
        self.wfile.write(PNG_BYTES)

    def log_message(self, format: str, *args: Any) -> None:
        return


class MiniMaxCaptureServer(AbstractContextManager["MiniMaxCaptureServer"]):
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self._response = response
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _MiniMaxCaptureHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "MiniMaxCaptureServer":
        _MiniMaxCaptureHandler.requests_seen = []
        _MiniMaxCaptureHandler.image_response = self._response
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
        _MiniMaxCaptureHandler.image_response = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    @property
    def image_url(self) -> str:
        return f"{self.base_url}/image.png"

    @property
    def requests_seen(self) -> list[dict[str, Any]]:
        return _MiniMaxCaptureHandler.requests_seen


def _generator(base_url: str) -> ImageGenerator:
    gen = ImageGenerator(api_key="test-key", base_url=base_url, model="image-01")
    gen.text_to_image_models = ["image-01"]
    gen.image_edit_models = ["image-01"]
    gen.max_retries = 1
    gen.timeout = 10
    return gen


def test_minimax_image_key_does_not_fall_back_to_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from config.settings import Settings

    monkeypatch.setattr(Settings, "IMAGE_API_KEY", None)
    monkeypatch.setattr(Settings, "OPENAI_API_KEY", "sk-openai-compatible-key")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

    assert Settings.get_image_api_key() is None

    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-key")
    assert Settings.get_image_api_key() == "sk-minimax-key"


def test_missing_minimax_image_key_is_safe_typed_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from config.settings import Settings

    monkeypatch.setattr(Settings, "IMAGE_API_KEY", None)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

    generator = ImageGenerator(api_key=None, base_url="https://api.minimaxi.com/v1")

    with pytest.raises(ImageProviderError) as raised:
        generator.require_generation_config()

    assert raised.value.code == "image_provider_not_configured"
    assert raised.value.category == "configuration"
    assert raised.value.retryable is False
    assert "API_KEY" not in raised.value.public_message


def test_text_to_image_posts_minimax_payload_and_downloads_url() -> None:
    with MiniMaxCaptureServer() as server:
        _MiniMaxCaptureHandler.image_response = {
            "id": "test-task",
            "data": {"image_urls": [server.image_url]},
            "metadata": {"success_count": "1", "failed_count": "0"},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }
        image_bytes, prompt_used = _generator(server.base_url).generate_image(
            prompt="A realistic quiet library at dusk",
            size="1664*928",
            n=2,
            extra_params={
                "seed": 123,
                "prompt_optimizer": True,
                "aigc_watermark": False,
                "negative_prompt": "low quality, distorted hands",
            },
        )

    assert image_bytes == PNG_BYTES
    assert prompt_used.startswith("A realistic quiet library")
    assert len(server.requests_seen) == 1

    request = server.requests_seen[0]
    assert request["path"] == "/v1/image_generation"
    assert request["authorization"] == "Bearer test-key"
    assert request["content_type"] == "application/json"

    body = request["body"]
    assert body["model"] == "image-01"
    assert "A realistic quiet library at dusk" in body["prompt"]
    assert "low quality, distorted hands" in body["prompt"]
    assert body["aspect_ratio"] == "16:9"
    assert body["response_format"] == "url"
    assert body["n"] == 2
    assert body["seed"] == 123
    assert body["prompt_optimizer"] is True
    assert "aigc_watermark" not in body
    assert "input" not in body
    assert "parameters" not in body
    assert "negative_prompt" not in body


def test_e2e_local_image_mode_returns_deterministic_png_without_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINIMAX_E2E_LOCAL_IMAGE", "1")

    with MiniMaxCaptureServer() as server:
        generator = _generator(server.base_url)
        image_bytes, prompt_used = generator.generate_image("local e2e prompt")
        url_image_bytes, url_prompt_used, image_url = generator.generate_image_with_url(
            "local e2e prompt with url"
        )
        edited_images = generator.edit_image(
            "http://example.invalid/reference.png",
            "local e2e edit prompt",
            num_images=2,
        )

    assert image_bytes == PNG_BYTES
    assert prompt_used == "local e2e prompt"
    assert url_image_bytes == PNG_BYTES
    assert url_prompt_used == "local e2e prompt with url"
    assert image_url.startswith("data:image/png;base64,")
    assert edited_images == [
        (PNG_BYTES, "local e2e edit prompt"),
        (PNG_BYTES, "local e2e edit prompt"),
    ]
    assert server.requests_seen == []


def test_minimax_success_with_empty_image_sources_raises_generation_error() -> None:
    response = {
        "id": "empty-success-task",
        "data": {"image_urls": ["", None]},
        "metadata": {"success_count": "0", "failed_count": "0"},
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }

    with MiniMaxCaptureServer(response=response) as server:
        with pytest.raises(ImageProviderError) as raised:
            _generator(server.base_url).generate_image("empty image output")

    assert raised.value.code == "image_provider_invalid_response"
    assert raised.value.category == "invalid_response"
    assert raised.value.retryable is False


def test_image_to_image_posts_subject_reference_and_returns_variants() -> None:
    with MiniMaxCaptureServer() as server:
        _MiniMaxCaptureHandler.image_response = {
            "id": "edit-task",
            "data": {"image_urls": [server.image_url, server.image_url]},
            "metadata": {"success_count": 2, "failed_count": 0},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }
        results = _generator(server.base_url).edit_image(
            reference_image="data:image/png;base64,abc123",
            prompt="Keep the same person, change the outfit to a white coat",
            size="928*1664",
            num_images=2,
        )

    assert results == [
        (PNG_BYTES, "Keep the same person, change the outfit to a white coat (variant 1)"),
        (PNG_BYTES, "Keep the same person, change the outfit to a white coat (variant 2)"),
    ]
    assert len(server.requests_seen) == 1

    body = server.requests_seen[0]["body"]
    assert body["model"] == "image-01"
    assert body["prompt"] == "Keep the same person, change the outfit to a white coat"
    assert body["aspect_ratio"] == "9:16"
    assert body["n"] == 2
    assert body["subject_reference"] == [
        {"type": "character", "image_file": "data:image/png;base64,abc123"}
    ]
    assert "aigc_watermark" not in body
    assert "input" not in body
    assert "parameters" not in body


def test_minimax_content_safety_code_raises_content_inspection_error() -> None:
    response = {
        "id": "blocked-task",
        "data": {"image_urls": []},
        "metadata": {"success_count": 0, "failed_count": 1},
        "base_resp": {"status_code": 1026, "status_msg": "sensitive prompt"},
    }

    with MiniMaxCaptureServer(response=response) as server:
        with pytest.raises(ContentInspectionError, match="内容安全审核"):
            _generator(server.base_url).edit_image(
                reference_image=server.image_url,
                prompt="blocked prompt",
                size="1328*1328",
            )


def test_minimax_nonzero_base_resp_raises_generation_error() -> None:
    response = {
        "id": "failed-task",
        "data": {"image_urls": []},
        "metadata": {"success_count": 0, "failed_count": 1},
        "base_resp": {"status_code": 1008, "status_msg": "insufficient balance"},
    }

    with MiniMaxCaptureServer(response=response) as server:
        with pytest.raises(ImageProviderError) as raised:
            _generator(server.base_url).generate_image("city at night")

    assert raised.value.code == "minimax_1008"
    assert raised.value.category == "capacity"
    assert raised.value.retryable is False
