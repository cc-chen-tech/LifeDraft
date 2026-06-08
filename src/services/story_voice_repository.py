"""Persistence helpers for story voice reading."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.database.models import GeneratedVoiceAsset, VoiceReadingJob, VoiceReadingSetting


class StoryVoiceReadingRepository:
    """Repository for voice settings, narration jobs, and generated assets."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_settings(self, user_id: int) -> Optional[VoiceReadingSetting]:
        return (
            self.db.query(VoiceReadingSetting)
            .filter(VoiceReadingSetting.user_id == user_id)
            .one_or_none()
        )

    def upsert_settings(
        self,
        user_id: int,
        selected_voice_color: Optional[str],
        auto_read_enabled: Optional[bool],
    ) -> VoiceReadingSetting:
        setting = self.get_settings(user_id)
        if setting is None:
            setting = VoiceReadingSetting(user_id=user_id)
            self.db.add(setting)

        if selected_voice_color is not None:
            setattr(setting, "selected_voice_color", selected_voice_color)
        if auto_read_enabled is not None:
            setattr(setting, "auto_read_enabled", auto_read_enabled)
        self.db.flush()
        return setting

    def find_ready_asset(
        self,
        text_hash: str,
        voice_id: str,
        speed: float,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Optional[GeneratedVoiceAsset]:
        query = (
            self.db.query(GeneratedVoiceAsset)
            .filter(
                GeneratedVoiceAsset.text_hash == text_hash,
                GeneratedVoiceAsset.voice_id == voice_id,
                GeneratedVoiceAsset.speed == speed,
                GeneratedVoiceAsset.status == "ready",
            )
        )
        if provider is not None:
            query = query.filter(GeneratedVoiceAsset.provider == provider)
        if model is not None:
            query = query.filter(GeneratedVoiceAsset.model == model)
        if user_id is not None:
            query = query.filter(GeneratedVoiceAsset.user_id == user_id)
        return query.order_by(GeneratedVoiceAsset.created_at.desc()).first()

    def create_asset(
        self,
        user_id: int,
        context: Dict[str, Any],
        voice_id: str,
        speed: float,
        provider: str,
        model: str,
        storage_path: str,
        duration_ms: int,
        status: str,
    ) -> GeneratedVoiceAsset:
        asset = GeneratedVoiceAsset(
            user_id=user_id,
            source_type=str(context["source_type"]),
            context_json=context,
            text_hash=str(context["text_hash"]),
            voice_id=voice_id,
            speed=speed,
            provider=provider,
            model=model,
            storage_path=storage_path,
            duration_ms=duration_ms,
            status=status,
        )
        self.db.add(asset)
        self.db.flush()
        return asset

    def create_job(
        self,
        user_id: int,
        context: Dict[str, Any],
        voice_id: str,
        speed: float,
        status: str,
        asset_id: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> VoiceReadingJob:
        job = VoiceReadingJob(
            user_id=user_id,
            asset_id=asset_id,
            context_json=context,
            text_hash=str(context["text_hash"]),
            voice_id=voice_id,
            speed=speed,
            status=status,
            error_code=error_code,
            error_message=error_message,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def get_job(self, job_id: int, user_id: int) -> Optional[VoiceReadingJob]:
        return (
            self.db.query(VoiceReadingJob)
            .filter(VoiceReadingJob.job_id == job_id, VoiceReadingJob.user_id == user_id)
            .one_or_none()
        )
