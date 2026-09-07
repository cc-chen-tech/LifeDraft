"""A live, stalled WebSocket must release the TTS worker within its budget."""

import json
import threading
import time
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from websockets.sync.server import serve

from src.services.minimax_config import MiniMaxConfig
from src.services.minimax_story_tts_provider import MiniMaxWebSocketTTSClient

pytestmark = pytest.mark.unit


@contextmanager
def provider_server(handler):
    with serve(handler, "127.0.0.1", 0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"ws://127.0.0.1:{server.socket.getsockname()[1]}"
        finally:
            server.shutdown()
            thread.join(timeout=2)


@pytest.mark.parametrize("stage", ["connection", "task_start", "audio"])
def test_stalled_receive_has_an_actual_deadline(stage, monkeypatch, tmp_path):
    release = threading.Event()

    def handler(socket):
        if stage != "connection":
            socket.send(json.dumps({"event": "connected_success"}))
            socket.recv()
        if stage == "audio":
            socket.send(json.dumps({"event": "task_started"}))
            socket.recv()
        release.wait(0.8)

    monkeypatch.delenv("MINIMAX_E2E_LOCAL_AUDIO", raising=False)
    try:
        with provider_server(handler) as url:
            config = MiniMaxConfig.from_env(
                env={
                    "MINIMAX_API_KEY": "test-only",
                    "MINIMAX_TTS_WEBSOCKET_URL": url,
                    "MINIMAX_TIMEOUT_SECONDS": "0.15",
                },
                voice_asset_dir=tmp_path,
            )
            start = time.monotonic()
            with pytest.raises(TimeoutError):
                MiniMaxWebSocketTTSClient(config).synthesize_to_file(
                    {"text": "等待测试。"}, tmp_path / "audio.mp3"
                )
            assert time.monotonic() - start < 0.6
            assert not (tmp_path / "audio.mp3").exists()
    finally:
        release.set()


def test_non_audio_messages_do_not_extend_audio_idle_budget(monkeypatch, tmp_path):
    from websockets.sync import client as websocket_client
    from src.services import minimax_story_tts_provider as provider_module

    clock = {"now": 0.0}

    class StatusOnlySocket:
        def __init__(self):
            self.startup = ["connected_success", "task_started"]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def send(self, message):
            pass

        def recv(self, timeout=None):
            if self.startup:
                return json.dumps({"event": self.startup.pop(0)})
            clock["now"] += min(1.0, timeout or 1.0)
            return json.dumps({"event": "task_continued"})

    monkeypatch.delenv("MINIMAX_E2E_LOCAL_AUDIO", raising=False)
    monkeypatch.setattr(websocket_client, "connect", lambda *a, **k: StatusOnlySocket())
    monkeypatch.setattr(provider_module, "time", SimpleNamespace(monotonic=lambda: clock["now"]))
    config = MiniMaxConfig.from_env(env={"MINIMAX_API_KEY": "test-only"}, voice_asset_dir=tmp_path)
    with pytest.raises(TimeoutError, match="audio"):
        MiniMaxWebSocketTTSClient(config).synthesize_to_file({"text": "等待。"}, tmp_path / "audio.mp3")
    assert clock["now"] <= 15.0, "provider status frames concealed missing audio"
