"""Contracts for MiniMax story narration and generated music providers."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.database.models import Game, SessionLocal, init_db
from src.services.music_service import MusicBrief
from src.services.story_tts_provider import BrowserSpeechTTSProvider


def test_minimax_config_defaults_are_secret_free_and_provider_specific(tmp_path: Path) -> None:
    from src.services.minimax_config import MiniMaxConfig

    config = MiniMaxConfig.from_env(
        env={},
        voice_asset_dir=tmp_path / "voice",
        music_asset_dir=tmp_path / "music",
    )

    assert config.api_key is None
    assert config.tts_model.startswith("speech-")
    assert config.tts_async_create_url == "https://api.minimaxi.com/v1/t2a_async_v2"
    assert config.tts_async_query_url == "https://api.minimaxi.com/v1/query/t2a_async_query_v2"
    assert config.file_retrieve_url == "https://api.minimaxi.com/v1/files/retrieve_content"
    assert config.music_model == "music-2.6"
    assert config.music_generation_url.startswith("https://api.minimaxi.com/")
    assert config.request_timeout_seconds == 180.0
    assert config.music_generation_enabled is True
    assert config.story_auto_read_default_enabled is False
    assert config.voice_asset_dir == tmp_path / "voice"
    assert config.music_asset_dir == tmp_path / "music"


def test_minimax_tts_without_credentials_reports_browser_fallback(tmp_path: Path) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_story_tts_provider import MiniMaxTTSProvider

    provider = MiniMaxTTSProvider(
        config=MiniMaxConfig.from_env(
            env={},
            voice_asset_dir=tmp_path / "voice",
            music_asset_dir=tmp_path / "music",
        )
    )

    metadata = provider.metadata()
    speech = provider.synthesize(
        {
            "text_hash": "story-hash",
            "text": "这段故事应该在无凭证时走浏览器朗读。",
        },
        "warm_female",
        1.0,
    )

    assert metadata.provider == "minimax"
    assert metadata.available is False
    assert metadata.playback_mode == "browser_speech"
    assert speech == BrowserSpeechTTSProvider().synthesize(
        {"text_hash": "story-hash", "text": "这段故事应该在无凭证时走浏览器朗读。"},
        "warm_female",
        1.0,
    )


def test_minimax_tts_request_payload_uses_story_text_voice_speed_and_model(tmp_path: Path) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_story_tts_provider import MiniMaxTTSProvider

    provider = MiniMaxTTSProvider(
        config=MiniMaxConfig.from_env(
            env={"MINIMAX_API_KEY": "test-key", "MINIMAX_TTS_MODEL": "speech-02-turbo"},
            voice_asset_dir=tmp_path / "voice",
            music_asset_dir=tmp_path / "music",
        )
    )

    payload = provider.build_async_create_payload(
        text="雨夜码头的旧账册被风吹开。",
        voice_id="warm_female",
        speed=1.15,
    )

    encoded = json.dumps(payload, ensure_ascii=False)
    assert "speech-02-turbo" in encoded
    assert "雨夜码头的旧账册被风吹开。" in encoded
    assert "warm_female" not in encoded
    assert "speed" in encoded
    assert "1.15" in encoded


def test_minimax_tts_over_limit_story_text_falls_back_without_audio(tmp_path: Path) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_story_tts_provider import MiniMaxTTSProvider

    provider = MiniMaxTTSProvider(
        config=MiniMaxConfig.from_env(
            env={"MINIMAX_API_KEY": "test-key", "MINIMAX_TTS_MAX_CHARS": "100"},
            voice_asset_dir=tmp_path / "voice",
            music_asset_dir=tmp_path / "music",
        )
    )
    speech = provider.synthesize(
        {
            "text_hash": "too-long",
            "text": "雨夜码头" * 40,
        },
        "warm_female",
        1.0,
    )

    assert speech.playback_mode == "browser_speech"
    assert speech.storage_path is None
    assert not (tmp_path / "voice").exists()


def test_music_brief_for_minimax_generation_is_bounded_and_instrumental() -> None:
    from src.services.minimax_music_generation import MiniMaxMusicGenerationProvider

    long_story = "雨夜码头的旧账册被风吹开。" * 200
    brief = MiniMaxMusicGenerationProvider.build_brief_from_story(
        story_text=long_story,
        analysis={
            "mood": "紧张",
            "scene_type": "雨夜追逐",
            "environment": "民国码头",
            "pacing": "急促",
            "energy": "高",
            "instruments": ["鼓", "大提琴"],
            "negative_cues": ["人声", "歌词"],
        },
        max_prompt_chars=420,
    )

    assert isinstance(brief, MusicBrief)
    assert brief.mood == "紧张"
    assert brief.scene_type == "雨夜追逐"
    assert "instrumental" in brief.generation_prompt.lower()
    assert "no vocals" in brief.generation_prompt.lower()
    assert len(brief.generation_prompt) <= 420
    assert long_story not in brief.generation_prompt


def test_minimax_music_generation_request_uses_url_output_and_audio_settings() -> None:
    from src.services.minimax_music_generation import MiniMaxMusicGenerationRequest

    brief = MusicBrief.from_analysis(
        {
            "mood": "紧张",
            "scene_type": "夜袭",
            "environment": "古风山林",
            "pacing": "急促",
            "energy": "高",
            "instruments": ["鼓", "笛子"],
            "negative_cues": ["人声", "歌词"],
        }
    )
    request = MiniMaxMusicGenerationRequest.from_brief(
        game_id=101,
        brief=brief,
        model="music-2.6",
    )

    payload = request.to_payload()

    assert payload["model"] == "music-2.6"
    assert payload["output_format"] == "url"
    assert payload["is_instrumental"] is True
    assert payload["audio_setting"]["sample_rate"] >= 32000
    assert payload["audio_setting"]["bitrate"] == 256000
    assert payload["audio_setting"]["format"] in {"mp3", "wav"}
    assert "instrumental" in payload["prompt"].lower()
    assert "no vocals" in payload["prompt"].lower()


def test_generated_minimax_track_contract_matches_frontend_queue_consumer() -> None:
    from src.services.minimax_music_generation import MiniMaxMusicGenerationProvider

    track = MiniMaxMusicGenerationProvider.to_playlist_track(
        asset_id=88,
        title="AI 雨夜码头",
        audio_url="/api/music/generated/88.mp3",
        duration_ms=63000,
        provider="minimax",
        model="music-2.6",
        brief_hash="brief-hash-88",
    )

    assert track["id"] == "ai-generated-88"
    assert track["name"] == "AI 雨夜码头"
    assert track["url"] == "/api/music/generated/88.mp3"
    assert track["source"] == "ai_generated"
    assert track["provider"] == "minimax"
    assert track["model"] == "music-2.6"
    assert track["asset_id"] == 88
    assert track["brief_hash"] == "brief-hash-88"


def test_minimax_music_provider_uses_real_local_http_boundary(tmp_path: Path) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_music_generation import (
        MiniMaxMusicGenerationProvider,
        MiniMaxMusicGenerationRequest,
    )

    requests_seen: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            requests_seen.append(json.loads(body.decode("utf-8")))
            response = json.dumps(
                {"data": {"audio_url": f"http://127.0.0.1:{server.server_port}/asset.mp3"}}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def do_GET(self) -> None:
            audio = b"ID3\x04\x00\x00\x00\x00\x00\x00"
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(audio)))
            self.end_headers()
            self.wfile.write(audio)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        config = MiniMaxConfig.from_env(
            env={
                "MINIMAX_API_KEY": "test-key",
                "MINIMAX_MUSIC_GENERATION_URL": f"http://127.0.0.1:{server.server_port}/music",
            },
            voice_asset_dir=tmp_path / "voice",
            music_asset_dir=tmp_path / "music",
        )
        provider = MiniMaxMusicGenerationProvider(config=config)
        brief = MusicBrief.default()
        request = MiniMaxMusicGenerationRequest.from_brief(
            game_id=9001,
            brief=brief,
            model="music-2.6",
        )

        generated = provider.generate_to_asset(request, brief_hash="brief-local-http")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert requests_seen
    assert requests_seen[0]["model"] == "music-2.6"
    assert requests_seen[0]["output_format"] == "url"
    assert requests_seen[0]["audio_setting"]["bitrate"] == 256000
    assert generated.storage_path.startswith("/api/music/generated/")
    assert generated.local_path.is_file()
    assert generated.local_path.read_bytes().startswith(b"ID3")
    assert generated.duration_ms > 0


def test_minimax_music_provider_downloads_data_audio_url_from_real_local_http_boundary(
    tmp_path: Path,
) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_music_generation import (
        MiniMaxMusicGenerationProvider,
        MiniMaxMusicGenerationRequest,
    )

    requests_seen: list[dict[str, Any]] = []
    get_paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            requests_seen.append(json.loads(body.decode("utf-8")))
            response = json.dumps(
                {"data": {"audio": f"http://127.0.0.1:{server.server_port}/asset.mp3"}}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def do_GET(self) -> None:
            get_paths.append(self.path)
            audio = b"ID3\x04\x00\x00\x00\x00\x00\x00"
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(audio)))
            self.end_headers()
            self.wfile.write(audio)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        config = MiniMaxConfig.from_env(
            env={
                "MINIMAX_API_KEY": "test-key",
                "MINIMAX_MUSIC_GENERATION_URL": f"http://127.0.0.1:{server.server_port}/music",
            },
            voice_asset_dir=tmp_path / "voice",
            music_asset_dir=tmp_path / "music",
        )
        provider = MiniMaxMusicGenerationProvider(config=config)
        request = MiniMaxMusicGenerationRequest.from_brief(
            game_id=9004,
            brief=MusicBrief.default(),
            model="music-2.6",
        )

        generated = provider.generate_to_asset(request, brief_hash="brief-data-audio-url")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert requests_seen
    assert requests_seen[0]["is_instrumental"] is True
    assert get_paths == ["/asset.mp3"]
    assert generated.storage_path == "/api/music/generated/brief-data-audio-url-music-2.6.mp3"
    assert generated.local_path.read_bytes().startswith(b"ID3")


def test_minimax_music_provider_reports_base_resp_error_from_real_local_http_boundary(
    tmp_path: Path,
) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_music_generation import (
        MiniMaxMusicGenerationProvider,
        MiniMaxMusicGenerationRequest,
    )

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            response = json.dumps(
                {"base_resp": {"status_code": 1008, "status_msg": "insufficient balance"}}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        config = MiniMaxConfig.from_env(
            env={
                "MINIMAX_API_KEY": "test-key",
                "MINIMAX_MUSIC_GENERATION_URL": f"http://127.0.0.1:{server.server_port}/music",
            },
            voice_asset_dir=tmp_path / "voice",
            music_asset_dir=tmp_path / "music",
        )
        provider = MiniMaxMusicGenerationProvider(config=config)
        request = MiniMaxMusicGenerationRequest.from_brief(
            game_id=9005,
            brief=MusicBrief.default(),
            model="music-2.6",
        )

        try:
            provider.generate_to_asset(request, brief_hash="brief-provider-error")
        except RuntimeError as exc:
            error = str(exc)
        else:
            raise AssertionError("provider should report MiniMax business errors")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert "MiniMax music generation failed" in error
    assert "status_code=1008" in error
    assert "insufficient balance" in error


def test_minimax_music_provider_saves_hex_audio_response_from_real_local_http_boundary(
    tmp_path: Path,
) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_music_generation import (
        MiniMaxMusicGenerationProvider,
        MiniMaxMusicGenerationRequest,
    )

    audio = b"ID3\x04\x00\x00\x00\x00\x00\x00"
    requests_seen: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            requests_seen.append(json.loads(body.decode("utf-8")))
            response = json.dumps(
                {
                    "data": {"audio": audio.hex()},
                    "extra_info": {"music_duration": 25364},
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        config = MiniMaxConfig.from_env(
            env={
                "MINIMAX_API_KEY": "test-key",
                "MINIMAX_MUSIC_GENERATION_URL": f"http://127.0.0.1:{server.server_port}/music",
            },
            voice_asset_dir=tmp_path / "voice",
            music_asset_dir=tmp_path / "music",
        )
        provider = MiniMaxMusicGenerationProvider(config=config)
        request = MiniMaxMusicGenerationRequest.from_brief(
            game_id=9003,
            brief=MusicBrief.default(),
            model="music-2.6",
        )

        generated = provider.generate_to_asset(request, brief_hash="brief-hex-audio")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert requests_seen
    assert requests_seen[0]["output_format"] == "url"
    assert generated.storage_path == "/api/music/generated/brief-hex-audio-music-2.6.mp3"
    assert generated.media_type == "audio/mpeg"
    assert generated.duration_ms == 25364
    assert generated.local_path.read_bytes() == audio


def test_minimax_music_provider_local_audio_mode_writes_decodable_wav(tmp_path: Path) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_music_generation import (
        MiniMaxMusicGenerationProvider,
        MiniMaxMusicGenerationRequest,
    )

    config = MiniMaxConfig.from_env(
        env={
            "MINIMAX_API_KEY": "test-key",
            "MINIMAX_E2E_LOCAL_AUDIO": "1",
        },
        voice_asset_dir=tmp_path / "voice",
        music_asset_dir=tmp_path / "music",
    )
    provider = MiniMaxMusicGenerationProvider(config=config)
    request = MiniMaxMusicGenerationRequest.from_brief(
        game_id=9002,
        brief=MusicBrief.default(),
        model="music-2.6",
    )

    generated = provider.generate_to_asset(request, brief_hash="brief-local-audio")

    assert generated.storage_path == "/api/music/generated/brief-local-audio-music-2.6.wav"
    assert generated.media_type == "audio/wav"
    assert generated.local_path.read_bytes().startswith(b"RIFF")
    assert b"WAVE" in generated.local_path.read_bytes()[:16]


def test_generated_music_route_serves_provider_assets(tmp_path: Path) -> None:
    from src.api.routers.music import read_generated_music_file

    music_dir = tmp_path / "music"
    music_dir.mkdir()
    (music_dir / "ready-track.mp3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")
    nested = music_dir / "nested"
    nested.mkdir()
    (nested / "track.mp3").write_bytes(b"ID3")

    payload = read_generated_music_file("ready-track.mp3", asset_dir=music_dir)

    assert payload is not None
    assert payload.content.startswith(b"ID3")
    assert payload.media_type == "audio/mpeg"
    assert read_generated_music_file("../ready-track.mp3", asset_dir=music_dir) is None
    assert read_generated_music_file("nested/track.mp3", asset_dir=music_dir) is None


def test_music_generate_api_returns_ready_track_from_story_without_netease_blocking(
    tmp_path: Path,
) -> None:
    from src.api.routers.music import router

    init_db()
    session = SessionLocal()
    try:
        game = Game(language="zh", initial_state={"name": "MiniMax API Music"})
        session.add(game)
        session.commit()
        session.refresh(game)
        game_id = int(game.game_id)
    finally:
        session.close()

    previous_env = {
        name: os.environ.get(name)
        for name in ["MINIMAX_API_KEY", "MINIMAX_E2E_LOCAL_AUDIO", "STORY_MUSIC_ASSET_DIR"]
    }
    os.environ["MINIMAX_API_KEY"] = "test-key"
    os.environ["MINIMAX_E2E_LOCAL_AUDIO"] = "1"
    os.environ["STORY_MUSIC_ASSET_DIR"] = str(tmp_path / "music")
    try:
        app = FastAPI()
        app.include_router(router, prefix="/api")
        client = TestClient(app)

        response = client.post(
            "/api/music/generate",
            json={
                "game_id": game_id,
                "story_text": "雨夜码头的旧账册被风吹开，主角在汽笛声里追向江边。",
                "analysis": {
                    "mood": "紧张",
                    "scene_type": "雨夜追逐",
                    "environment": "民国码头",
                },
            },
        )
    finally:
        for name, value in previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    assert response.status_code == 200
    data = response.json()
    assert data["track"]["source"] == "ai_generated"
    assert data["track"]["provider"] == "minimax"
    assert data["track"]["url"].startswith("/api/music/generated/")
    assert data["track"]["url"].endswith(".wav")
    assert data["insert_policy"] == "future_queue"


def test_music_generate_api_reports_unexpected_generation_failure_without_global_500(
    tmp_path: Path,
) -> None:
    from src.api.routers.music import router

    init_db()
    session = SessionLocal()
    try:
        game = Game(language="zh", initial_state={"name": "MiniMax API Music Failure"})
        session.add(game)
        session.commit()
        session.refresh(game)
        game_id = int(game.game_id)
    finally:
        session.close()

    asset_path_that_is_file = tmp_path / "music-assets-file"
    asset_path_that_is_file.write_text("not a directory", encoding="utf-8")
    previous_env = {
        name: os.environ.get(name)
        for name in ["MINIMAX_API_KEY", "MINIMAX_E2E_LOCAL_AUDIO", "STORY_MUSIC_ASSET_DIR"]
    }
    os.environ["MINIMAX_API_KEY"] = "test-key"
    os.environ["MINIMAX_E2E_LOCAL_AUDIO"] = "1"
    os.environ["STORY_MUSIC_ASSET_DIR"] = str(asset_path_that_is_file)
    try:
        app = FastAPI()
        app.include_router(router, prefix="/api")
        client = TestClient(app)

        response = client.post(
            "/api/music/generate",
            json={
                "game_id": game_id,
                "story_text": "雨夜码头的旧账册被风吹开，主角在汽笛声里追向江边。",
                "analysis": {
                    "mood": "紧张",
                    "scene_type": "雨夜追逐",
                    "environment": "民国码头",
                },
            },
        )
    finally:
        for name, value in previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "AI music generation failed" in detail
    assert "FileExistsError" in detail
    assert str(asset_path_that_is_file) not in detail


def test_music_generation_request_uses_independent_analysis_defaults() -> None:
    from src.api.routers.music import MusicGenerationRequest

    analysis_field = MusicGenerationRequest.model_fields["analysis"]
    assert analysis_field.default_factory is dict

    first = MusicGenerationRequest(game_id=1, story_text="雨夜码头")
    second = MusicGenerationRequest(game_id=2, story_text="山林夜袭")
    first.analysis["mood"] = "紧张"

    assert second.analysis == {}
    assert first.analysis is not second.analysis


def test_minimax_tts_client_uses_real_local_async_http_boundary(tmp_path: Path) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_story_tts_provider import MiniMaxAsyncTTSClient

    payloads_seen: list[dict[str, Any]] = []
    query_paths_seen: list[str] = []
    audio_bytes = b"ID3\x04\x00\x00\x00\x00\x00\x00"

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            payloads_seen.append(json.loads(body.decode("utf-8")))
            response = json.dumps(
                {
                    "task_id": 95157322514444,
                    "file_id": 95157322514496,
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def do_GET(self) -> None:
            query_paths_seen.append(self.path)
            if self.path.startswith("/query"):
                response = json.dumps(
                    {
                        "task_id": 95157322514444,
                        "status": "success",
                        "file_id": 95157322514496,
                        "base_resp": {"status_code": 0, "status_msg": "success"},
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
                return
            if self.path.startswith("/file"):
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(audio_bytes)))
                self.end_headers()
                self.wfile.write(audio_bytes)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        config = MiniMaxConfig.from_env(
            env={
                "MINIMAX_API_KEY": "test-key",
                "MINIMAX_TTS_ASYNC_CREATE_URL": f"{base_url}/create",
                "MINIMAX_TTS_ASYNC_QUERY_URL": f"{base_url}/query",
                "MINIMAX_FILE_RETRIEVE_URL": f"{base_url}/file",
            },
            voice_asset_dir=tmp_path / "voice",
            music_asset_dir=tmp_path / "music",
        )
        output_path = tmp_path / "voice.mp3"
        MiniMaxAsyncTTSClient(config).synthesize_to_file(
            {"model": "speech-02-turbo", "text": "雨夜码头"},
            output_path,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert payloads_seen
    assert payloads_seen[0]["text"] == "雨夜码头"
    assert any("task_id=95157322514444" in path for path in query_paths_seen)
    assert any("file_id=95157322514496" in path for path in query_paths_seen)
    assert output_path.read_bytes() == audio_bytes


def test_minimax_tts_client_downloads_file_metadata_url_from_real_local_http_boundary(
    tmp_path: Path,
) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_story_tts_provider import MiniMaxAsyncTTSClient

    request_paths_seen: list[str] = []
    audio_bytes = b"ID3\x04\x00\x00\x00\x00\x00\x00"

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            response = json.dumps(
                {
                    "task_id": 95157322515555,
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def do_GET(self) -> None:
            request_paths_seen.append(self.path)
            if self.path.startswith("/query"):
                response = json.dumps(
                    {
                        "task_id": 95157322515555,
                        "status": "success",
                        "file_id": 95157322516666,
                        "base_resp": {"status_code": 0, "status_msg": "success"},
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
                return
            if self.path.startswith("/file"):
                response = json.dumps(
                    {
                        "file": {
                            "file_id": 95157322516666,
                            "download_url": f"http://127.0.0.1:{server.server_port}/download.mp3",
                        }
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
                return
            if self.path.startswith("/download.mp3"):
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(audio_bytes)))
                self.end_headers()
                self.wfile.write(audio_bytes)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        config = MiniMaxConfig.from_env(
            env={
                "MINIMAX_API_KEY": "test-key",
                "MINIMAX_TTS_ASYNC_CREATE_URL": f"{base_url}/create",
                "MINIMAX_TTS_ASYNC_QUERY_URL": f"{base_url}/query",
                "MINIMAX_FILE_RETRIEVE_URL": f"{base_url}/file",
            },
            voice_asset_dir=tmp_path / "voice",
            music_asset_dir=tmp_path / "music",
        )
        output_path = tmp_path / "voice.mp3"
        MiniMaxAsyncTTSClient(config).synthesize_to_file(
            {"model": "speech-02-turbo", "text": "雨夜码头"},
            output_path,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert any("file_id=95157322516666" in path for path in request_paths_seen)
    assert "/download.mp3" in request_paths_seen
    assert output_path.read_bytes() == audio_bytes


def test_minimax_tts_client_rejects_non_http_urls_before_network_io(tmp_path: Path) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_story_tts_provider import MiniMaxAsyncTTSClient

    config = MiniMaxConfig.from_env(
        env={
            "MINIMAX_API_KEY": "test-key",
            "MINIMAX_TTS_ASYNC_CREATE_URL": f"file://{tmp_path}/create.json",
        },
        voice_asset_dir=tmp_path / "voice",
        music_asset_dir=tmp_path / "music",
    )

    output_path = tmp_path / "voice.mp3"
    try:
        MiniMaxAsyncTTSClient(config).synthesize_to_file(
            {"model": "speech-02-turbo", "text": "雨夜码头"},
            output_path,
        )
    except ValueError as exc:
        assert "http" in str(exc).lower()
    else:
        raise AssertionError("MiniMax async TTS client accepted a non-http URL")

    assert not output_path.exists()
