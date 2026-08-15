"""Provider-free MiniMax narration fallback and local-audio contracts."""

import hashlib
from pathlib import Path

import pytest

from src.services.minimax_config import MiniMaxConfig
from src.services.minimax_story_tts_provider import MiniMaxAsyncTTSClient, MiniMaxTTSProvider
from src.services.story_tts_provider import TTSProviderUnavailableError, build_deterministic_wav


def _config(tmp_path: Path, env: dict[str, str]) -> MiniMaxConfig:
    return MiniMaxConfig.from_env(
        env=env,
        voice_asset_dir=tmp_path / "voice",
    )


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
