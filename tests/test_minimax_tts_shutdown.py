"""MiniMax cancellation propagates through actual socket/process wait boundaries."""

import json
import os
import shutil
import subprocess
import sys
import time
from threading import Event

import pytest

from src.services.minimax_config import MiniMaxConfig
from src.services.minimax_story_tts_provider import MiniMaxTTSProvider
from src.services.story_tts_provider import TTSSynthesisCancelled
from tests.test_minimax_tts_receive_deadlines import provider_server

pytestmark = pytest.mark.unit


def test_stalled_websocket_cancels_at_heartbeat_without_publishing_audio(tmp_path, monkeypatch):
    receiving = Event()
    release = Event()

    def handler(socket):
        socket.send(json.dumps({"event": "connected_success"}))
        socket.recv()
        socket.send(json.dumps({"event": "task_started"}))
        socket.recv()
        receiving.set()
        release.wait(8)

    def checkpoint():
        if receiving.is_set():
            raise TTSSynthesisCancelled("shutdown")

    monkeypatch.delenv("MINIMAX_E2E_LOCAL_AUDIO", raising=False)
    try:
        with provider_server(handler) as url:
            provider = MiniMaxTTSProvider(config=MiniMaxConfig.from_env(
                env={"MINIMAX_API_KEY": "test", "MINIMAX_TTS_WEBSOCKET_URL": url,
                     "MINIMAX_TIMEOUT_SECONDS": "180"}, voice_asset_dir=tmp_path,
            ))
            started = time.monotonic()
            with pytest.raises(TTSSynthesisCancelled):
                provider.synthesize_scene({"text_hash": "cancelled", "text": "等待。"},
                                          "warm_female", 1.0, on_progress=checkpoint)
            assert time.monotonic() - started < 7
            assert not list(tmp_path.iterdir()), "cancelled temporary audio was retained"
    finally:
        release.set()


@pytest.mark.parametrize("stage", ["assembly", "padding"])
def test_cancel_stalled_ffmpeg_reaps_child_and_cleans_temporary_audio(tmp_path, monkeypatch, stage):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg required to build valid MP3 fixture")
    original = tmp_path / "original.mp3"
    subprocess.run([ffmpeg, "-nostdin", "-y", "-f", "lavfi", "-i",
                    "anullsrc=r=32000:cl=mono", "-t", "0.1", str(original)],
                   check=True, capture_output=True, timeout=5)
    pid_file = tmp_path / "child.pid"
    stalled_ffmpeg = tmp_path / "stalled-ffmpeg"
    stalled_ffmpeg.write_text(
        f"#!{sys.executable}\nimport os,time\nfrom pathlib import Path\n"
        f"Path({str(pid_file)!r}).write_text(str(os.getpid()) + ' ' + str(time.monotonic()))\ntime.sleep(30)\n"
    )
    stalled_ffmpeg.chmod(0o755)
    monkeypatch.setattr("src.services.minimax_story_tts_provider.shutil.which", lambda _: str(stalled_ffmpeg))
    monkeypatch.delenv("MINIMAX_E2E_LOCAL_AUDIO", raising=False)
    assets = tmp_path / "assets"
    assets.mkdir()
    scene = assets / "ready.mp3"
    scene.write_bytes(original.read_bytes())

    class AudioClient:
        def synthesize_to_file(self, payload, output_path, on_progress=None):
            output_path.write_bytes(original.read_bytes())

    provider = MiniMaxTTSProvider(config=MiniMaxConfig.from_env(
        env={"MINIMAX_API_KEY": "test", "MINIMAX_TIMEOUT_SECONDS": "30"}, voice_asset_dir=assets,
    ))
    provider.websocket_client = AudioClient()

    def checkpoint():
        if pid_file.exists():
            raise TTSSynthesisCancelled("shutdown")

    context = {"text_hash": "cancelled", "text": "等待。", "pause_after_ms": 100}
    started = time.monotonic()
    with pytest.raises(TTSSynthesisCancelled):
        if stage == "assembly":
            provider.assemble_scenes([str(scene)], context, "warm_female", 1.0, on_progress=checkpoint)
        else:
            provider.synthesize_scene(context, "warm_female", 1.0, on_progress=checkpoint)
    assert time.monotonic() - started < 9
    assert pid_file.exists(), "cancellation must exercise a running child"
    pid, child_started = pid_file.read_text().split()
    assert time.monotonic() - float(child_started) < 6.5
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid), 0)
    assert list(assets.iterdir()) == [scene], "cancelled output leaked or ready scene was removed"


@pytest.mark.parametrize("outcome", ["success", "error", "timeout"])
def test_ffmpeg_retains_exit_errors_and_total_deadline(tmp_path, outcome):
    from src.services.minimax_story_tts_provider import _run_ffmpeg

    marker = tmp_path / "process.pid"
    # Ignore TERM to exercise the bounded kill/reap path on a total timeout.
    code = (
        "import os,signal,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"Path({str(marker)!r}).write_text(str(os.getpid())); "
        + {"success": "pass", "error": "raise SystemExit(7)", "timeout": "time.sleep(30)"}[outcome]
    )
    argv = [sys.executable, "-c", code]
    started = time.monotonic()
    if outcome == "success":
        _run_ffmpeg(argv, timeout_seconds=1, on_progress=None)
    elif outcome == "error":
        with pytest.raises(subprocess.CalledProcessError) as error:
            _run_ffmpeg(argv, timeout_seconds=1, on_progress=None)
        assert error.value.returncode == 7
    else:
        with pytest.raises(subprocess.TimeoutExpired):
            _run_ffmpeg(argv, timeout_seconds=0.2, on_progress=None)
    assert time.monotonic() - started < 2
    with pytest.raises(ProcessLookupError):
        os.kill(int(marker.read_text()), 0)
