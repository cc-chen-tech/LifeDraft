"""Story voice reading service and deterministic local TTS provider."""

from __future__ import annotations

import hashlib
import os
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
from src.services.story_tts_provider import (
    BrowserSpeechTTSProvider,
    DeterministicTTSProvider,
    StoryTTSProvider,
    build_deterministic_wav,
    build_story_tts_provider,
)

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


class StoryVoiceReadingService:
    """Application service for settings, reading requests, and job recovery."""

    def __init__(
        self,
        repository: StoryVoiceReadingRepository,
        provider: Optional[StoryTTSProvider] = None,
        validator: Optional[ReadingContextValidator] = None,
    ) -> None:
        self.repository = repository
        self.provider = provider or build_story_tts_provider()
        self.validator = validator or ReadingContextValidator()

    def get_settings(self, user_id: int) -> VoiceReadingSettingsResponse:
        settings = self.repository.get_settings(user_id)
        provider_metadata = self.provider.metadata()
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
            tts_provider=provider_metadata.provider,
            tts_model=provider_metadata.model,
            tts_provider_available=provider_metadata.available,
            backend_audio_enabled=provider_metadata.backend_audio_enabled,
            playback_mode=provider_metadata.playback_mode,
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
        request_provider_enabled = os.getenv("STORY_TTS_ALLOW_REQUEST_PROVIDER", "0") == "1"
        provider = (
            build_story_tts_provider(request.preferred_provider)
            if request_provider_enabled and request.preferred_provider is not None
            else self.provider
        )
        provider_metadata = provider.metadata()
        if not provider_metadata.backend_audio_enabled:
            job = self.repository.create_job(
                user_id=user_id,
                context=context,
                voice_id=request.voice_id,
                speed=request.speed,
                status="ready",
            )
            return StoryVoiceReadingResponse(
                job_id=int(job.job_id),
                status="ready",
                audio_url=None,
                asset_id=None,
                duration_ms=None,
                playback_mode="browser_speech",
                provider=provider_metadata.provider,
                model=provider_metadata.model,
                media_type=None,
                message="Use browser speech synthesis for story reading",
            )

        ready_asset = self.repository.find_ready_asset(
            text_hash=str(context["text_hash"]),
            voice_id=request.voice_id,
            speed=request.speed,
            provider=provider_metadata.provider,
            model=provider_metadata.model,
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
                playback_mode="audio",
                provider=str(ready_asset.provider),
                model=str(ready_asset.model),
                media_type="audio/wav",
                message="Reused cached reading audio",
            )

        speech = provider.synthesize(context, request.voice_id, request.speed)
        if speech.playback_mode != "audio" or speech.storage_path is None or speech.duration_ms is None:
            job = self.repository.create_job(
                user_id=user_id,
                context=context,
                voice_id=request.voice_id,
                speed=request.speed,
                status="ready",
            )
            return StoryVoiceReadingResponse(
                job_id=int(job.job_id),
                status="ready",
                audio_url=None,
                asset_id=None,
                duration_ms=None,
                playback_mode=speech.playback_mode,
                provider=speech.provider,
                model=speech.model,
                media_type=speech.media_type,
                message="Use browser speech synthesis for story reading",
            )

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
            playback_mode=speech.playback_mode,
            provider=speech.provider,
            model=speech.model,
            media_type=speech.media_type,
            message="Generated reading audio",
        )

    def get_job(self, user_id: int, job_id: int) -> VoiceReadingJobResponse:
        job = self.repository.get_job(job_id, user_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        asset = job.asset
        playback_mode = "audio" if asset is not None else "browser_speech"
        return VoiceReadingJobResponse(
            job_id=int(job.job_id),
            status=str(job.status),
            audio_url=str(asset.storage_path) if asset is not None else None,
            asset_id=int(asset.asset_id) if asset is not None else None,
            duration_ms=int(asset.duration_ms) if asset is not None else None,
            playback_mode=playback_mode,
            provider=str(asset.provider) if asset is not None else "browser",
            model=str(asset.model) if asset is not None else "browser-speech",
            media_type="audio/wav" if asset is not None else None,
            error_code=str(job.error_code) if job.error_code is not None else None,
            message=str(job.error_message) if job.error_message is not None else "",
        )


def normalize_text_hash(text: str) -> str:
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
