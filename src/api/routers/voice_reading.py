"""Story voice reading API routes."""

from __future__ import annotations

from typing import Generator

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.api.schemas import (
    MessageResponse,
    StoryVoiceReadingRequest,
    StoryVoiceReadingResponse,
    VoiceReadingJobResponse,
    VoiceReadingSettingsResponse,
    VoiceReadingSettingsUpdateRequest,
    VoiceUploadConsentRequest,
)
from src.database.models import SessionLocal
from src.services.story_tts_provider import read_generated_voice_file
from src.services.story_voice_reading import StoryVoiceReadingService, build_deterministic_wav
from src.services.story_voice_repository import StoryVoiceReadingRepository

router = APIRouter()


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_service(db: Session) -> StoryVoiceReadingService:
    return StoryVoiceReadingService(StoryVoiceReadingRepository(db))


@router.get("/settings", response_model=VoiceReadingSettingsResponse)
async def get_voice_reading_settings(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> VoiceReadingSettingsResponse:
    return get_service(db).get_settings(user_id)


@router.patch("/settings", response_model=VoiceReadingSettingsResponse)
async def update_voice_reading_settings(
    request: VoiceReadingSettingsUpdateRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> VoiceReadingSettingsResponse:
    service = get_service(db)
    response = service.update_settings(
        user_id=user_id,
        selected_voice_color=request.selected_voice_color,
        auto_read_enabled=request.auto_read_enabled,
    )
    db.commit()
    return response


@router.post("/read", response_model=StoryVoiceReadingResponse)
async def request_story_reading(
    request: StoryVoiceReadingRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> StoryVoiceReadingResponse:
    response = get_service(db).request_reading(user_id, request)
    db.commit()
    return response


@router.get("/jobs/{job_id}", response_model=VoiceReadingJobResponse)
async def get_voice_reading_job(
    job_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> VoiceReadingJobResponse:
    return get_service(db).get_job(user_id, job_id)


@router.get("/audio/{file_name}")
async def get_voice_reading_audio(file_name: str) -> Response:
    if not file_name.endswith(".wav"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    generated_audio = read_generated_voice_file(file_name)
    if generated_audio is not None:
        return Response(
            content=generated_audio,
            media_type="audio/wav",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )
    stem = file_name[:-4]
    marker = "-"
    if marker not in stem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    text_hash, voice_id = stem.rsplit(marker, 1)
    if not text_hash or not voice_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    return Response(
        content=build_deterministic_wav(text_hash, voice_id),
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.post("/upload-consent", response_model=MessageResponse)
async def upload_voice_consent(
    request: VoiceUploadConsentRequest,
    user_id: int = Depends(get_current_user),
) -> MessageResponse:
    if not request.consent_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "voice_consent_required",
                "message": "Voice upload requires explicit consent",
                "field": "consent_confirmed",
            },
        )
    return MessageResponse(
        message="Custom voice upload is gated for future provider setup",
        success=True,
        data={"user_id": user_id, "sample_name": request.sample_name},
    )
