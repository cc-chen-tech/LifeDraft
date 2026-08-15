"""Provider-backed story text-to-speech adapters."""

from __future__ import annotations

import hashlib
import math
import os
import struct
import wave
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Protocol

from config.settings import PROJECT_ROOT

PlaybackMode = Literal["audio", "unavailable"]
MIN_DETERMINISTIC_AUDIO_DURATION_SECONDS = 8.0


class TTSProviderUnavailableError(RuntimeError):
    """Raised when high-quality narration cannot be produced."""


@dataclass(frozen=True)
class StoryTTSProviderMetadata:
    provider: str
    model: str
    playback_mode: PlaybackMode
    media_type: Optional[str]
    available: bool
    backend_audio_enabled: bool


@dataclass(frozen=True)
class GeneratedSpeech:
    storage_path: Optional[str]
    duration_ms: Optional[int]
    provider: str
    model: str
    media_type: Optional[str]
    playback_mode: PlaybackMode


class StoryTTSProvider(Protocol):
    provider: str
    model: str

    def metadata(self) -> StoryTTSProviderMetadata:
        """Return provider availability and playback behavior."""

    def synthesize(self, context: Dict[str, Any], voice_id: str, speed: float) -> GeneratedSpeech:
        """Synthesize or select playback for a reading context."""


class UnavailableTTSProvider:
    """Test fixture for exercising explicit high-quality-provider failure."""

    provider = "unavailable"
    model = "unavailable"

    def metadata(self) -> StoryTTSProviderMetadata:
        return StoryTTSProviderMetadata(
            provider=self.provider,
            model=self.model,
            playback_mode="unavailable",
            media_type=None,
            available=False,
            backend_audio_enabled=False,
        )

    def synthesize(self, context: Dict[str, Any], voice_id: str, speed: float) -> GeneratedSpeech:
        raise TTSProviderUnavailableError("High-quality narration is unavailable")


class DeterministicTTSProvider:
    """Local deterministic provider used for development and tests."""

    provider = "local"
    model = "deterministic-v1"

    def metadata(self) -> StoryTTSProviderMetadata:
        return StoryTTSProviderMetadata(
            provider=self.provider,
            model=self.model,
            playback_mode="audio",
            media_type="audio/wav",
            available=True,
            backend_audio_enabled=True,
        )

    def synthesize(self, context: Dict[str, Any], voice_id: str, speed: float) -> GeneratedSpeech:
        text = str(context["text"])
        text_hash = str(context["text_hash"])
        duration = max(
            int(MIN_DETERMINISTIC_AUDIO_DURATION_SECONDS * 1000),
            int(len(text) * 120 / speed),
        )
        return GeneratedSpeech(
            storage_path=f"/api/voice-reading/audio/{text_hash}-{voice_id}.wav",
            duration_ms=duration,
            provider=self.provider,
            model=self.model,
            media_type="audio/wav",
            playback_mode="audio",
        )


def build_story_tts_provider() -> StoryTTSProvider:
    """Return the sole production narration provider."""

    from src.services.minimax_story_tts_provider import MiniMaxTTSProvider

    return MiniMaxTTSProvider()


def build_deterministic_wav(text_hash: str, voice_id: str) -> bytes:
    sample_rate = 16_000
    duration_seconds = MIN_DETERMINISTIC_AUDIO_DURATION_SECONDS
    frequency_offsets = {
        "warm_female": 0,
        "calm_male": -70,
        "clear_neutral": 35,
    }
    base_frequency = 440 + frequency_offsets.get(voice_id, 0)
    seed = int(hashlib.sha256(f"{text_hash}:{voice_id}".encode("utf-8")).hexdigest()[:4], 16)
    frequency = base_frequency + (seed % 60)
    amplitude = 9_000
    frame_count = int(sample_rate * duration_seconds)

    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for index in range(frame_count):
            envelope = min(1.0, index / 600, (frame_count - index) / 600)
            sample = int(amplitude * envelope * math.sin(2 * math.pi * frequency * index / sample_rate))
            frames.extend(struct.pack("<h", sample))
        wav.writeframes(bytes(frames))
    return buffer.getvalue()


def read_generated_voice_file(file_name: str) -> Optional[bytes]:
    configured_dir = os.getenv("STORY_TTS_ASSET_DIR")
    asset_dir = Path(configured_dir) if configured_dir else PROJECT_ROOT / "data" / "voice_assets"
    file_path = (asset_dir / file_name).resolve()
    try:
        file_path.relative_to(asset_dir.resolve())
    except ValueError:
        return None
    if not file_path.is_file():
        return None
    return file_path.read_bytes()
