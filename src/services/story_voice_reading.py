"""Story voice reading service and deterministic local TTS provider."""

from __future__ import annotations

import hashlib
import math
import struct
import wave
from io import BytesIO
from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from src.api.schemas import (
    ReadingContext,
    StoryVoiceReadingRequest,
    StoryVoiceReadingResponse,
    VoiceReadingJobResponse,
    VoiceReadingSettingsResponse,
)
from src.services.story_voice_repository import StoryVoiceReadingRepository

AVAILABLE_VOICES = ["warm_female", "calm_male", "clear_neutral"]


class ReadingContextValidator:
    """Validate reading context without falling back to latest game state."""

    def validate(self, context: ReadingContext) -> Dict[str, Any]:
        source_type = context.source_type
        if source_type not in {"current_story", "history_round", "summary", "ending"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "invalid_source_type",
                    "message": "Unsupported reading source type",
                    "field": "source_type",
                },
            )
        if source_type in {"current_story", "history_round"}:
            missing = [
                field
                for field, value in (
                    ("week", context.week),
                    ("round_number", context.round_number),
                    ("stage", context.stage),
                )
                if value is None
            ]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error_code": "missing_context_identity",
                        "message": "Story reading context is missing round identity",
                        "field": ",".join(missing),
                    },
                )

        normalized_hash = normalize_text_hash(context.text)
        if context.text_hash != normalized_hash:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "text_hash_mismatch",
                    "message": "Reading text hash does not match text",
                    "field": "text_hash",
                },
            )
        return context.model_dump()


@dataclass(frozen=True)
class GeneratedSpeech:
    storage_path: str
    duration_ms: int
    provider: str
    model: str


class DeterministicTTSProvider:
    """Local deterministic provider used for development and tests."""

    provider = "local"
    model = "deterministic-v1"

    def synthesize(self, context: Dict[str, Any], voice_id: str, speed: float) -> GeneratedSpeech:
        text = str(context["text"])
        text_hash = str(context["text_hash"])
        duration = max(2_400, int(len(text) * 120 / speed))
        return GeneratedSpeech(
            storage_path=f"/api/voice-reading/audio/{text_hash}-{voice_id}.wav",
            duration_ms=duration,
            provider=self.provider,
            model=self.model,
        )


class StoryVoiceReadingService:
    """Application service for settings, reading requests, and job recovery."""

    def __init__(
        self,
        repository: StoryVoiceReadingRepository,
        provider: Optional[DeterministicTTSProvider] = None,
        validator: Optional[ReadingContextValidator] = None,
    ) -> None:
        self.repository = repository
        self.provider = provider or DeterministicTTSProvider()
        self.validator = validator or ReadingContextValidator()

    def get_settings(self, user_id: int) -> VoiceReadingSettingsResponse:
        settings = self.repository.get_settings(user_id)
        return VoiceReadingSettingsResponse(
            member_required=False,
            enabled=True,
            available_voice_colors=AVAILABLE_VOICES,
            selected_voice_color=(
                str(settings.selected_voice_color)
                if settings is not None and settings.selected_voice_color is not None
                else "warm_female"
            ),
            uploaded_voice_available=False,
            auto_read_enabled=(
                bool(settings.auto_read_enabled) if settings is not None else False
            ),
        )

    def update_settings(
        self,
        user_id: int,
        selected_voice_color: Optional[str],
        auto_read_enabled: Optional[bool],
    ) -> VoiceReadingSettingsResponse:
        if selected_voice_color is not None and selected_voice_color not in AVAILABLE_VOICES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "unsupported_voice",
                    "message": "Selected voice is not available",
                    "field": "selected_voice_color",
                },
            )
        self.repository.upsert_settings(user_id, selected_voice_color, auto_read_enabled)
        return self.get_settings(user_id)

    def request_reading(
        self,
        user_id: int,
        request: StoryVoiceReadingRequest,
    ) -> StoryVoiceReadingResponse:
        if request.voice_id not in AVAILABLE_VOICES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "unsupported_voice",
                    "message": "Selected voice is not available",
                    "field": "voice_id",
                },
            )
        context = self.validator.validate(request.context)
        ready_asset = self.repository.find_ready_asset(
            text_hash=str(context["text_hash"]),
            voice_id=request.voice_id,
            speed=request.speed,
        )
        if ready_asset is not None:
            job = self.repository.create_job(
                user_id=user_id,
                context=context,
                voice_id=request.voice_id,
                speed=request.speed,
                status="ready",
                asset_id=int(ready_asset.asset_id),
            )
            return StoryVoiceReadingResponse(
                job_id=int(job.job_id),
                status="ready",
                audio_url=str(ready_asset.storage_path),
                asset_id=int(ready_asset.asset_id),
                duration_ms=int(ready_asset.duration_ms),
                message="Reused cached reading audio",
            )

        speech = self.provider.synthesize(context, request.voice_id, request.speed)
        asset = self.repository.create_asset(
            user_id=user_id,
            context=context,
            voice_id=request.voice_id,
            speed=request.speed,
            provider=speech.provider,
            model=speech.model,
            storage_path=speech.storage_path,
            duration_ms=speech.duration_ms,
            status="ready",
        )
        job = self.repository.create_job(
            user_id=user_id,
            context=context,
            voice_id=request.voice_id,
            speed=request.speed,
            status="ready",
            asset_id=int(asset.asset_id),
        )
        return StoryVoiceReadingResponse(
            job_id=int(job.job_id),
            status="ready",
            audio_url=speech.storage_path,
            asset_id=int(asset.asset_id),
            duration_ms=speech.duration_ms,
            message="Generated reading audio",
        )

    def get_job(self, user_id: int, job_id: int) -> VoiceReadingJobResponse:
        job = self.repository.get_job(job_id, user_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        asset = job.asset
        return VoiceReadingJobResponse(
            job_id=int(job.job_id),
            status=str(job.status),
            audio_url=str(asset.storage_path) if asset is not None else None,
            asset_id=int(asset.asset_id) if asset is not None else None,
            duration_ms=int(asset.duration_ms) if asset is not None else None,
            error_code=str(job.error_code) if job.error_code is not None else None,
            message=str(job.error_message) if job.error_message is not None else "",
        )


def normalize_text_hash(text: str) -> str:
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_deterministic_wav(text_hash: str, voice_id: str) -> bytes:
    sample_rate = 16_000
    duration_seconds = 2.4
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
