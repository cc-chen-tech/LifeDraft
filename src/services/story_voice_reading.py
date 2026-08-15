"""Story voice reading service and deterministic local TTS provider."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from src.api.schemas import (
    ReadingContext,
    StoryVoiceReadingRequest,
    StoryVoiceReadingResponse,
    VoiceReadingJobResponse,
    VoiceReadingSegmentResponse,
    VoiceReadingSettingsResponse,
)
from src.database.models import VOICE_ASSET_VERSION
from src.services.minimax_config import build_minimax_config
from src.services.story_voice_repository import StoryVoiceReadingRepository
from src.services.story_tts_provider import (
    DeterministicTTSProvider,
    StoryTTSProvider,
    build_deterministic_wav,
    build_story_tts_provider,
)

__all__ = [
    "DeterministicTTSProvider",
    "ReadingContextValidator",
    "StoryVoiceReadingService",
    "build_deterministic_wav",
    "media_type_for_voice_asset",
    "normalize_text_hash",
    "split_story_paragraphs",
]

AVAILABLE_VOICES = ["warm_female", "calm_male", "clear_neutral"]


class ReadingContextValidator:
    """Validate reading context without falling back to latest game state."""

    def validate(self, context: ReadingContext) -> Dict[str, Any]:
        source_type = context.source_type
        if source_type != "current_story":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "current_story_only",
                    "message": "Only the current day's story can be narrated",
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
                bool(settings.auto_read_enabled)
                if settings is not None
                else story_auto_read_default_enabled()
            ),
            selected_speed=(
                float(settings.selected_speed)
                if settings is not None and settings.selected_speed is not None
                else 1.0
            ),
            tts_provider=provider_metadata.provider,
            tts_model=provider_metadata.model,
            tts_provider_available=provider_metadata.available,
            backend_audio_enabled=provider_metadata.backend_audio_enabled,
            playback_mode=("audio" if provider_metadata.backend_audio_enabled else "unavailable"),
        )

    def update_settings(
        self,
        user_id: int,
        selected_voice_color: Optional[str],
        auto_read_enabled: Optional[bool],
        selected_speed: Optional[float] = None,
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
        self.repository.upsert_settings(
            user_id, selected_voice_color, auto_read_enabled, selected_speed
        )
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
        provider = self.provider
        provider_metadata = provider.metadata()
        paragraphs = split_story_paragraphs(str(context["text"]))
        dedupe_key = normalize_text_hash(
            ":".join(
                [
                    str(user_id),
                    str(context["text_hash"]),
                    request.voice_id,
                    str(request.speed),
                    provider_metadata.provider,
                    provider_metadata.model,
                    f"asset-v{VOICE_ASSET_VERSION}",
                ]
            )
        )
        job = self.repository.find_job_by_dedupe_key(dedupe_key)
        if job is None:
            try:
                job = self.repository.create_chapter_job(
                    user_id=user_id,
                    context=context,
                    voice_id=request.voice_id,
                    speed=request.speed,
                    dedupe_key=dedupe_key,
                    paragraphs=paragraphs,
                )
            except IntegrityError:
                # Another request created the same chapter between our lookup
                # and insert. Roll back only this request transaction and reuse
                # the committed winner instead of surfacing a duplicate error.
                self.repository.db.rollback()
                job = self.repository.find_job_by_dedupe_key(dedupe_key)
                if job is None:
                    raise
        elif str(job.status) == "failed":
            self.repository.mark_job_queued_for_retry(job)
        elif str(job.status) == "processing":
            self.repository.requeue_stale_processing_job(user_id, int(job.job_id))
            job = self.repository.get_job(int(job.job_id), user_id)
            if job is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        if not provider_metadata.backend_audio_enabled:
            setattr(job, "status", "failed")
            setattr(job, "error_code", "tts_provider_unavailable")
            setattr(
                job,
                "error_message",
                "High-quality narration is temporarily unavailable",
            )
            for segment in job.segments:
                segment.status = "failed"
                segment.error_code = "tts_provider_unavailable"
                segment.error_message = job.error_message
            self.repository.db.flush()
        return self._reading_response(job, provider_metadata.provider, provider_metadata.model)

    def process_job(self, user_id: int, job_id: int) -> VoiceReadingJobResponse:
        job = self.repository.get_job(job_id, user_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        if str(job.status) == "ready":
            return self.get_job(user_id, job_id)

        lease_token = self.repository.claim_queued_job_for_processing_with_token(
            user_id, job_id
        )
        if lease_token is None:
            return self.get_job(user_id, job_id)
        job = self.repository.get_job(job_id, user_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        metadata = self.provider.metadata()
        if not metadata.backend_audio_enabled:
            if (
                self.repository.commit_processing_changes(
                    user_id,
                    job_id,
                    lease_token,
                    terminal_status="failed",
                    error_code="tts_provider_unavailable",
                    error_message="High-quality narration is temporarily unavailable",
                )
                is None
            ):
                return self.get_job(user_id, job_id)
            return self.get_job(user_id, job_id)

        primary_asset_assigned = job.asset_id is not None
        for segment in job.segments:
            if str(segment.status) == "ready":
                continue
            segment.status = "processing"
            next_token = self.repository.commit_processing_changes(
                user_id, job_id, lease_token
            )
            if next_token is None:
                return self.get_job(user_id, job_id)
            lease_token = next_token
            segment_context = dict(job.context_json)
            segment_context["text"] = str(segment.text_content)
            segment_context["text_hash"] = str(segment.text_hash)
            ready_asset = self.repository.find_ready_asset(
                text_hash=str(segment.text_hash),
                voice_id=str(job.voice_id),
                speed=float(job.speed),
                provider=metadata.provider,
                model=metadata.model,
                user_id=user_id,
            )
            if ready_asset is not None and not self._is_valid_cached_asset(ready_asset):
                self.repository.invalidate_asset(
                    ready_asset,
                    "Generated MiniMax audio is missing or invalid",
                )
                ready_asset = None
            try:
                if ready_asset is None:
                    speech = self.provider.synthesize(
                        segment_context, str(job.voice_id), float(job.speed)
                    )
                    if (
                        speech.playback_mode != "audio"
                        or speech.storage_path is None
                        or speech.duration_ms is None
                    ):
                        raise RuntimeError("provider returned no high-quality audio")
                    ready_asset = self.repository.create_asset(
                        user_id=user_id,
                        context=segment_context,
                        voice_id=str(job.voice_id),
                        speed=float(job.speed),
                        provider=speech.provider,
                        model=speech.model,
                        storage_path=speech.storage_path,
                        duration_ms=speech.duration_ms,
                        status="ready",
                    )
                segment.asset = ready_asset
                segment.status = "ready"
                segment.error_code = None
                segment.error_message = None
                # Make each ready paragraph visible immediately so the client can
                # begin playback while later paragraphs continue generating.
                primary_asset_id = (
                    int(ready_asset.asset_id) if not primary_asset_assigned else None
                )
                next_token = self.repository.commit_processing_changes(
                    user_id,
                    job_id,
                    lease_token,
                    primary_asset_id=primary_asset_id,
                )
                if next_token is None:
                    return self.get_job(user_id, job_id)
                lease_token = next_token
                primary_asset_assigned = True
            except Exception as error:
                segment.status = "failed"
                segment.error_code = "tts_generation_failed"
                segment.error_message = str(error)
                if (
                    self.repository.commit_processing_changes(
                        user_id,
                        job_id,
                        lease_token,
                        terminal_status="failed",
                        error_code="tts_generation_failed",
                        error_message="High-quality narration could not be generated",
                    )
                    is None
                ):
                    return self.get_job(user_id, job_id)
                return self.get_job(user_id, job_id)

        if (
            self.repository.commit_processing_changes(
                user_id,
                job_id,
                lease_token,
                terminal_status="ready",
            )
            is None
        ):
            return self.get_job(user_id, job_id)
        return self.get_job(user_id, job_id)

    def _is_valid_cached_asset(self, asset: Any) -> bool:
        validator = getattr(self.provider, "is_valid_cached_asset", None)
        if not callable(validator):
            return True
        return bool(validator(str(asset.storage_path)))

    def get_job(self, user_id: int, job_id: int) -> VoiceReadingJobResponse:
        job = self.repository.get_job(job_id, user_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        metadata = self.provider.metadata()
        response = self._reading_response(job, metadata.provider, metadata.model)
        return VoiceReadingJobResponse(**response.model_dump())

    def _reading_response(
        self, job: Any, provider: str, model: str
    ) -> StoryVoiceReadingResponse:
        segments = [self._segment_response(segment) for segment in job.segments]
        first_ready = next((segment for segment in segments if segment.audio_url), None)
        if first_ready is None and job.asset is not None:
            first_ready = VoiceReadingSegmentResponse(
                paragraph_index=0,
                status="ready",
                audio_url=str(job.asset.storage_path),
                asset_id=int(job.asset.asset_id),
                duration_ms=int(job.asset.duration_ms),
                media_type=media_type_for_voice_asset(str(job.asset.storage_path)),
            )
            if not segments:
                segments = [first_ready]
        playback_mode = "audio" if first_ready is not None else "unavailable"
        error_code = (
            str(job.error_code)
            if job.error_code is not None
            else None
        )
        message = (
            str(job.error_message)
            if job.error_message is not None
            else ""
        )
        return StoryVoiceReadingResponse(
            job_id=int(job.job_id),
            status=str(job.status),
            audio_url=first_ready.audio_url if first_ready is not None else None,
            asset_id=first_ready.asset_id if first_ready is not None else None,
            duration_ms=first_ready.duration_ms if first_ready is not None else None,
            playback_mode=playback_mode,
            provider=provider,
            model=model,
            media_type=first_ready.media_type if first_ready is not None else None,
            error_code=error_code,
            message=message,
            segments=segments,
        )

    @staticmethod
    def _segment_response(segment: Any) -> VoiceReadingSegmentResponse:
        asset = segment.asset
        storage_path = str(asset.storage_path) if asset is not None else None
        return VoiceReadingSegmentResponse(
            paragraph_index=int(segment.paragraph_index),
            status=str(segment.status),
            audio_url=storage_path,
            asset_id=int(asset.asset_id) if asset is not None else None,
            duration_ms=int(asset.duration_ms) if asset is not None else None,
            media_type=media_type_for_voice_asset(storage_path) if storage_path else None,
            error_code=str(segment.error_code) if segment.error_code else None,
        )


def media_type_for_voice_asset(storage_path: str) -> str:
    suffix = storage_path.rsplit("?", 1)[0].rsplit(".", 1)[-1].lower()
    if suffix in {"mp3", "mpeg"}:
        return "audio/mpeg"
    if suffix == "m4a":
        return "audio/mp4"
    if suffix == "ogg":
        return "audio/ogg"
    return "audio/wav"


def story_auto_read_default_enabled() -> bool:
    return build_minimax_config().story_auto_read_default_enabled


def normalize_text_hash(text: str) -> str:
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def split_story_paragraphs(text: str) -> list[str]:
    """Return stable, non-empty story paragraphs while preserving internal line breaks."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n+", normalized) if paragraph.strip()]
