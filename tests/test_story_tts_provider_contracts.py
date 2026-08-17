from __future__ import annotations

import wave
from io import BytesIO
import pytest

from src.services.story_tts_provider import (
    DeterministicTTSProvider,
    TTSProviderUnavailableError,
    UnavailableTTSProvider,
    build_deterministic_wav,
    build_story_tts_provider,
    read_generated_voice_file,
)

pytestmark = [pytest.mark.unit]



def test_unavailable_provider_cannot_synthesize() -> None:
    provider = UnavailableTTSProvider()

    metadata = provider.metadata()
    with pytest.raises(TTSProviderUnavailableError):
        provider.synthesize({"text": "hello", "text_hash": "reading"}, "warm_female", 1.0)

    assert metadata.provider == "unavailable"
    assert metadata.model == "unavailable"
    assert metadata.playback_mode == "unavailable"
    assert metadata.media_type is None
    assert metadata.available is False
    assert metadata.backend_audio_enabled is False


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


def test_deterministic_wav_builder_returns_playable_fixed_length_audio() -> None:
    audio_data = build_deterministic_wav("reading-hash", "warm_female")

    with wave.open(BytesIO(audio_data), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 16_000
        assert wav.getnframes() == 128_000


def test_story_tts_provider_factory_is_minimax_only() -> None:
    from src.services.minimax_story_tts_provider import MiniMaxTTSProvider

    assert isinstance(build_story_tts_provider(), MiniMaxTTSProvider)


def test_read_generated_voice_file_rejects_path_escape_without_touching_disk() -> None:
    assert read_generated_voice_file("../escaped.wav") is None
