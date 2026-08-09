"""Loopback-only MiniMax image provider contracts for the maintained gate."""

from __future__ import annotations

import json
import threading
from contextlib import AbstractContextManager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

import pytest

from src.ai.image_exceptions import ImageProviderError
from src.ai.image_generator import ImageGenerator


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04"
    b"\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _MiniMaxLoopbackHandler(BaseHTTPRequestHandler):
    requests_seen: ClassVar[list[dict[str, Any]]] = []
    image_count: ClassVar[int] = 1
    response_status: ClassVar[int] = 0

    def do_POST(self) -> None:  # noqa: N802
        raw_body = self.rfile.read(int(self.headers["Content-Length"]))
        self.requests_seen.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "content_type": self.headers.get("Content-Type"),
                "body": json.loads(raw_body.decode("utf-8")),
            }
        )
        image_url = f"http://127.0.0.1:{self.server.server_port}/image.png"
        payload = {
            "id": "local-contract-task",
            "data": {"image_urls": [image_url] * self.image_count},
            "metadata": {"success_count": self.image_count, "failed_count": 0},
            "base_resp": {
                "status_code": self.response_status,
                "status_msg": "ok" if self.response_status == 0 else "capacity exhausted",
            },
        }
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/image.png":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(PNG_BYTES)))
        self.end_headers()
        self.wfile.write(PNG_BYTES)

    def log_message(self, format: str, *args: Any) -> None:
        return


class MiniMaxLoopbackServer(AbstractContextManager["MiniMaxLoopbackServer"]):
    def __init__(self, *, image_count: int = 1, response_status: int = 0) -> None:
        self._image_count = image_count
        self._response_status = response_status
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _MiniMaxLoopbackHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "MiniMaxLoopbackServer":
        _MiniMaxLoopbackHandler.requests_seen = []
        _MiniMaxLoopbackHandler.image_count = self._image_count
        _MiniMaxLoopbackHandler.response_status = self._response_status
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    @property
    def requests_seen(self) -> list[dict[str, Any]]:
        return _MiniMaxLoopbackHandler.requests_seen


def _generator(base_url: str) -> ImageGenerator:
    generator = ImageGenerator(api_key="local-contract-key", base_url=base_url, model="image-01")
    generator.text_to_image_models = ["image-01"]
    generator.image_edit_models = ["image-01"]
    generator.max_retries = 1
    generator.timeout = 10
    return generator


def test_text_generation_uses_minimax_payload_and_downloads_loopback_image() -> None:
    with MiniMaxLoopbackServer() as server:
        image_bytes, prompt = _generator(server.base_url).generate_image(
            prompt="maintained contract text generation",
            size="1664*928",
            n=2,
            extra_params={"seed": 17, "negative_prompt": "blurred"},
        )

    assert image_bytes == PNG_BYTES
    assert prompt == "maintained contract text generation"
    assert len(server.requests_seen) == 1
    request = server.requests_seen[0]
    assert request["path"] == "/v1/image_generation"
    assert request["authorization"] == "Bearer local-contract-key"
    assert request["content_type"] == "application/json"
    assert request["body"] == {
        "model": "image-01",
        "prompt": "maintained contract text generation\nAvoid: blurred",
        "response_format": "url",
        "n": 2,
        "prompt_optimizer": True,
        "aspect_ratio": "16:9",
        "seed": 17,
    }


def test_image_edit_submits_subject_reference_and_returns_all_loopback_variants() -> None:
    with MiniMaxLoopbackServer(image_count=2) as server:
        results = _generator(server.base_url).edit_image(
            reference_image="data:image/png;base64,AA==",
            prompt="maintained contract image edit",
            size="928*1664",
            num_images=2,
        )

    assert results == [
        (PNG_BYTES, "maintained contract image edit (variant 1)"),
        (PNG_BYTES, "maintained contract image edit (variant 2)"),
    ]
    assert len(server.requests_seen) == 1
    assert server.requests_seen[0]["body"] == {
        "model": "image-01",
        "prompt": "maintained contract image edit",
        "response_format": "url",
        "n": 2,
        "prompt_optimizer": True,
        "aspect_ratio": "9:16",
        "subject_reference": [
            {"type": "character", "image_file": "data:image/png;base64,AA=="}
        ],
    }


def test_generate_image_with_url_returns_loopback_source_url() -> None:
    with MiniMaxLoopbackServer() as server:
        image_bytes, prompt, image_url = _generator(server.base_url).generate_image_with_url(
            "maintained contract generation with url"
        )

    assert image_bytes == PNG_BYTES
    assert prompt == "maintained contract generation with url"
    assert image_url == f"{server.base_url}/image.png"
    assert len(server.requests_seen) == 1


def test_provider_capacity_status_is_a_typed_non_retryable_error() -> None:
    with MiniMaxLoopbackServer(response_status=1008) as server:
        with pytest.raises(ImageProviderError) as raised:
            _generator(server.base_url).generate_image("maintained contract provider capacity")

    assert raised.value.code == "minimax_1008"
    assert raised.value.category == "capacity"
    assert raised.value.retryable is False
