"""Provider-free MiniMax narration fallback and local-audio contracts."""

import hashlib
from pathlib import Path
import wave

import pytest

from src.services.minimax_config import MiniMaxConfig
from src.services.minimax_story_tts_provider import MiniMaxAsyncTTSClient, MiniMaxTTSProvider
from src.services.story_tts_provider import TTSProviderUnavailableError, build_deterministic_wav


def _config(tmp_path: Path, env: dict[str, str]) -> MiniMaxConfig:
    return MiniMaxConfig.from_env(
        env=env,
        voice_asset_dir=tmp_path / "voice",
    )


def test_minimax_tts_defaults_to_current_turbo_model(tmp_path: Path) -> None:
    config = _config(tmp_path, {})

    assert config.tts_model == "speech-2.8-turbo"


def test_missing_minimax_credential_reports_unavailable_without_fallback(tmp_path: Path) -> None:
    provider = MiniMaxTTSProvider(config=_config(tmp_path, {}))

    metadata = provider.metadata()
    with pytest.raises(TTSProviderUnavailableError):
        provider.synthesize(
            {"text_hash": "fallback-story", "text": "无凭证时不降级浏览器朗读。"},
            "warm_female",
            1.0,
        )

    assert metadata.available is False
    assert metadata.playback_mode == "unavailable"
    assert metadata.backend_audio_enabled is False


def test_local_audio_synthesis_writes_and_reuses_deterministic_wav(tmp_path: Path) -> None:
    provider = MiniMaxTTSProvider(
        config=_config(tmp_path, {"MINIMAX_E2E_LOCAL_AUDIO": "true"})
    )
    context = {"text_hash": "local-story", "text": "本地音频必须可复用且不依赖网络。"}

    first = provider.synthesize(context, "calm_male", 1.25)
    second = provider.synthesize(context, "calm_male", 1.25)
    artifact = tmp_path / "voice" / Path(str(first.storage_path)).name

    assert provider.metadata().media_type == "audio/wav"
    assert first.playback_mode == "audio"
    assert first.media_type == "audio/wav"
    assert first.storage_path == second.storage_path
    assert first.duration_ms == second.duration_ms
    assert artifact.read_bytes().startswith(b"RIFF")


def test_local_audio_is_validated_measured_and_atomically_published(tmp_path: Path) -> None:
    class RecordingClient:
        def __init__(self) -> None:
            self.output_paths: list[Path] = []

        def synthesize_to_file(
            self,
            payload: dict[str, object],
            output_path: Path,
            on_progress=None,
        ) -> str:
            if on_progress is not None:
                on_progress()
            self.output_paths.append(output_path)
            with wave.open(str(output_path), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(8_000)
                audio.writeframes(b"\x00\x00" * 1_000)
            return (
                "1\n00:00:00,000 --> 00:00:00,060\n第一段。\n\n"
                "2\n00:00:00,065 --> 00:00:00,125\n第二段。\n"
            )

    client = RecordingClient()
    provider = MiniMaxTTSProvider(
        config=_config(tmp_path, {"MINIMAX_E2E_LOCAL_AUDIO": "true"}),
        client=client,  # type: ignore[arg-type]
    )

    speech = provider.synthesize(
        {
            "text_hash": "atomic-story",
            "text": "第一段。\n\n第二段。",
            "paragraphs": ["第一段。", "第二段。"],
        },
        "calm_male",
        1.25,
    )
    asset_dir = tmp_path / "voice"
    published = asset_dir / Path(str(speech.storage_path)).name

    assert client.output_paths[0].parent == asset_dir
    assert client.output_paths[0] != published
    assert "speed-float64-3ff4000000000000" in published.name
    assert "cache-v3" in published.name
    assert published.exists()
    assert list(asset_dir.glob(".*")) == []
    assert speech.duration_ms == 125
    assert [
        (cue.paragraph_index, cue.start_ms, cue.end_ms)
        for cue in speech.paragraph_cues
    ] == [(0, 0, 65), (1, 65, 125)]


def test_close_accepted_speeds_use_distinct_v3_cache_tokens(tmp_path: Path) -> None:
    provider = MiniMaxTTSProvider(
        config=_config(tmp_path, {"MINIMAX_E2E_LOCAL_AUDIO": "true"})
    )
    context = {"text_hash": "close-speed-story", "text": "相近语速不能共享缓存文件。"}

    first = provider.synthesize(context, "warm_female", 1.0001)
    second = provider.synthesize(context, "warm_female", 1.0002)

    assert first.storage_path != second.storage_path
    assert "speed-float64-" in str(first.storage_path)
    assert "speed-float64-" in str(second.storage_path)


def test_invalid_minimax_mp3_is_rejected_and_temporary_file_is_removed(tmp_path: Path) -> None:
    class InvalidMp3Client:
        def synthesize_to_file(
            self,
            payload: dict[str, object],
            output_path: Path,
            on_progress=None,
        ) -> None:
            if on_progress is not None:
                on_progress()
            output_path.write_bytes(b"not an mp3")

    provider = MiniMaxTTSProvider(
        config=_config(tmp_path, {"MINIMAX_API_KEY": "configured"}),
        client=InvalidMp3Client(),  # type: ignore[arg-type]
    )

    with pytest.raises(TTSProviderUnavailableError):
        provider.synthesize(
            {"text_hash": "invalid-mp3", "text": "格式错误的 MiniMax 音频不可发布。"},
            "warm_female",
            1.0,
        )

    asset_dir = tmp_path / "voice"
    assert list(asset_dir.iterdir()) == []


def test_local_async_audio_uses_stable_sha256_text_hash(tmp_path: Path) -> None:
    text = "本地音频必须跨 Python 进程保持一致。"
    output_path = tmp_path / "local.wav"
    client = MiniMaxAsyncTTSClient(
        _config(tmp_path, {"MINIMAX_E2E_LOCAL_AUDIO": "true"})
    )

    client.synthesize_to_file({"text": text}, output_path)

    expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert output_path.read_bytes() == build_deterministic_wav(expected_hash, "warm_female")


def test_payload_and_oversized_text_keep_transport_and_failure_boundaries(tmp_path: Path) -> None:
    provider = MiniMaxTTSProvider(
        config=_config(
            tmp_path,
            {"MINIMAX_API_KEY": "configured", "MINIMAX_TTS_MAX_CHARS": "8"},
        )
    )

    async_payload = provider.build_async_create_payload("短文本", "clear_neutral", 0.9)
    websocket_payload = provider.build_websocket_start_payload("短文本", "clear_neutral", 0.9)
    with pytest.raises(TTSProviderUnavailableError):
        provider.synthesize(
            {"text_hash": "long-story", "text": "超过上限的文本不会使用浏览器朗读。"},
            "clear_neutral",
            1.0,
        )

    assert async_payload["language_boost"] == "auto"
    assert async_payload["voice_setting"]["voice_id"] == "female-yujie"
    assert websocket_payload["stream"] is False
    assert "language_boost" not in websocket_payload
    assert not (tmp_path / "voice").exists()
