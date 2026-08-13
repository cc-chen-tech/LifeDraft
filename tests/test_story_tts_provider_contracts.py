from __future__ import annotations

import wave
from io import BytesIO
from pathlib import Path

from src.services.story_tts_provider import (
    BrowserSpeechTTSProvider,
    DeterministicTTSProvider,
    OpenAICompatibleTTSProvider,
    _map_voice_id,
    _safe_file_token,
    build_deterministic_wav,
    build_story_tts_provider,
    read_generated_voice_file,
)


def test_browser_speech_provider_advertises_no_backend_asset() -> None:
    provider = BrowserSpeechTTSProvider()

    metadata = provider.metadata()
    speech = provider.synthesize({"text": "hello", "text_hash": "reading"}, "warm_female", 1.0)

    assert metadata.provider == "browser"
    assert metadata.model == "browser-speech"
    assert metadata.playback_mode == "browser_speech"
    assert metadata.media_type is None
    assert metadata.available is True
    assert metadata.backend_audio_enabled is False
    assert speech.storage_path is None
    assert speech.duration_ms is None
    assert speech.playback_mode == "browser_speech"


def test_deterministic_tts_provider_returns_stable_audio_metadata_and_duration() -> None:
    provider = DeterministicTTSProvider()

    metadata = provider.metadata()
    short_speech = provider.synthesize({"text": "short", "text_hash": "short-hash"}, "calm_male", 1.5)
    long_text = "story " * 120
    long_speech = provider.synthesize(
        {"text": long_text, "text_hash": "long-hash"},
        "clear_neutral",
        1.0,
    )

    assert metadata.provider == "local"
    assert metadata.model == "deterministic-v1"
    assert metadata.playback_mode == "audio"
    assert metadata.media_type == "audio/wav"
    assert metadata.available is True
    assert metadata.backend_audio_enabled is True
    assert short_speech.storage_path == "/api/voice-reading/audio/short-hash-calm_male.wav"
    assert short_speech.duration_ms == 8_000
    assert long_speech.duration_ms == len(long_text) * 120
    assert long_speech.media_type == "audio/wav"
    assert long_speech.playback_mode == "audio"


def test_story_tts_helpers_normalize_voice_and_filename_tokens() -> None:
    assert _map_voice_id("warm_female") == "alloy"
    assert _map_voice_id("calm_male") == "onyx"
    assert _map_voice_id("clear_neutral") == "nova"
    assert _map_voice_id("unknown") == "alloy"
    assert _safe_file_token(" model/v1 ++ ") == "model-v1"
    assert _safe_file_token("") == "unknown"
    assert _safe_file_token("中文") == "unknown"


def test_deterministic_wav_builder_returns_playable_fixed_length_audio() -> None:
    audio_data = build_deterministic_wav("reading-hash", "warm_female")

    with wave.open(BytesIO(audio_data), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 16_000
        assert wav.getnframes() == 128_000


def test_story_tts_provider_factory_uses_explicit_local_and_safe_fallback() -> None:
    assert isinstance(build_story_tts_provider("local"), DeterministicTTSProvider)
    assert isinstance(build_story_tts_provider("unknown"), BrowserSpeechTTSProvider)


def test_openai_compatible_provider_without_key_falls_back_to_browser(tmp_path: Path) -> None:
    provider = OpenAICompatibleTTSProvider(
        api_key="placeholder",
        base_url="https://voice.example/v1/",
        model="tts-model",
        asset_dir=tmp_path,
    )
    provider.api_key = ""

    metadata = provider.metadata()
    speech = provider.synthesize({"text": "read this", "text_hash": "reading"}, "warm_female", 1.0)

    assert provider.base_url == "https://voice.example/v1"
    assert provider.model == "tts-model"
    assert provider.asset_dir == tmp_path
    assert metadata.available is False
    assert metadata.backend_audio_enabled is False
    assert metadata.playback_mode == "browser_speech"
    assert speech.provider == "browser"
    assert speech.playback_mode == "browser_speech"


def test_read_generated_voice_file_rejects_path_escape_without_touching_disk() -> None:
    assert read_generated_voice_file("../escaped.wav") is None
