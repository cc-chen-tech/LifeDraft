"""Provider-backed story text-to-speech adapters."""

from __future__ import annotations

import hashlib
import math
import os
import re
import struct
import wave
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Protocol

import httpx

from config.settings import PROJECT_ROOT, settings

PlaybackMode = Literal["audio", "browser_speech"]
MIN_DETERMINISTIC_AUDIO_DURATION_SECONDS = 8.0


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


class BrowserSpeechTTSProvider:
    """Browser speech fallback; no backend audio asset is generated."""

    provider = "browser"
    model = "browser-speech"

    def metadata(self) -> StoryTTSProviderMetadata:
        return StoryTTSProviderMetadata(
            provider=self.provider,
            model=self.model,
            playback_mode="browser_speech",
            media_type=None,
            available=True,
            backend_audio_enabled=False,
        )

    def synthesize(self, context: Dict[str, Any], voice_id: str, speed: float) -> GeneratedSpeech:
        return GeneratedSpeech(
            storage_path=None,
            duration_ms=None,
            provider=self.provider,
            model=self.model,
            media_type=None,
            playback_mode="browser_speech",
        )


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


class OpenAICompatibleTTSProvider:
    """OpenAI-compatible speech provider using the /audio/speech API."""

    provider = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        asset_dir: Optional[Path] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("STORY_TTS_OPENAI_API_KEY") or settings.OPENAI_API_KEY
        self.base_url = (base_url or os.getenv("STORY_TTS_OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.getenv("STORY_TTS_OPENAI_MODEL") or "gpt-4o-mini-tts"
        configured_dir = os.getenv("STORY_TTS_ASSET_DIR")
        self.asset_dir = asset_dir or (Path(configured_dir) if configured_dir else PROJECT_ROOT / "data" / "voice_assets")

    def metadata(self) -> StoryTTSProviderMetadata:
        available = bool(self.api_key)
        return StoryTTSProviderMetadata(
            provider=self.provider,
            model=self.model,
            playback_mode="audio" if available else "browser_speech",
            media_type="audio/wav" if available else None,
            available=available,
            backend_audio_enabled=available,
        )

    def synthesize(self, context: Dict[str, Any], voice_id: str, speed: float) -> GeneratedSpeech:
        metadata = self.metadata()
        if not metadata.available or not self.api_key:
            return BrowserSpeechTTSProvider().synthesize(context, voice_id, speed)

        text_hash = str(context["text_hash"])
        safe_voice_id = _safe_file_token(voice_id)
        safe_provider = _safe_file_token(self.provider)
        safe_model = _safe_file_token(self.model)
        file_name = f"{text_hash}-{safe_voice_id}-{safe_provider}-{safe_model}.wav"
        self.asset_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.asset_dir / file_name
        if not output_path.exists():
            self._request_speech(str(context["text"]), voice_id, speed, output_path)
        return GeneratedSpeech(
            storage_path=f"/api/voice-reading/audio/{file_name}",
            duration_ms=max(1_000, int(len(str(context["text"])) * 120 / speed)),
            provider=self.provider,
            model=self.model,
            media_type="audio/wav",
            playback_mode="audio",
        )

    def _request_speech(self, text: str, voice_id: str, speed: float, output_path: Path) -> None:
        voice = _map_voice_id(voice_id)
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/audio/speech",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "voice": voice,
                    "input": text,
                    "speed": speed,
                    "response_format": "wav",
                },
            )
            response.raise_for_status()
            output_path.write_bytes(response.content)


def _map_voice_id(voice_id: str) -> str:
    return {
        "warm_female": "alloy",
        "calm_male": "onyx",
        "clear_neutral": "nova",
    }.get(voice_id, "alloy")


def _safe_file_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-_")
    return token or "unknown"


def build_story_tts_provider(provider_name: Optional[str] = None) -> StoryTTSProvider:
    env_provider = os.getenv("STORY_TTS_PROVIDER") or "browser"
    selected_provider = provider_name if provider_name is not None else env_provider
    provider = selected_provider.strip().lower()
    if provider == "local":
        return DeterministicTTSProvider()
    if provider == "openai":
        openai_provider = OpenAICompatibleTTSProvider()
        if openai_provider.metadata().available:
            return openai_provider
        return BrowserSpeechTTSProvider()
    if provider == "minimax":
        from src.services.minimax_story_tts_provider import MiniMaxTTSProvider

        minimax_provider = MiniMaxTTSProvider()
        if minimax_provider.metadata().available:
            return minimax_provider
        return BrowserSpeechTTSProvider()
    return BrowserSpeechTTSProvider()


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
