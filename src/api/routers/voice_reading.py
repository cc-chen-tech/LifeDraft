"""Story voice reading API routes."""

from __future__ import annotations

from typing import Optional


from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.types import Message, Receive, Scope, Send

from src.api.deps import get_current_user, get_session
from src.database.models import GeneratedVoiceAsset
from src.observability.diagnostics import emit_diagnostic
from src.api.schemas import (
    MessageResponse,
    StoryVoiceReadingRequest,
    StoryVoiceReadingResponse,
    VoiceReadingJobResponse,
    VoiceReadingProgressRequest,
    VoiceReadingProgressResponse,
    VoiceReadingSettingsResponse,
    VoiceReadingSettingsUpdateRequest,
    VoicePreviewRequest,
    VoicePreviewResponse,
    VoiceUploadConsentRequest,
)
from src.services.minimax_config import build_minimax_config
from src.services.story_tts_provider import generated_voice_file_path
from src.services.story_voice_reading import StoryVoiceReadingService, build_deterministic_wav
from src.services.story_voice_repository import StoryVoiceReadingRepository
from src.services.story_voice_progress import ProgressStoreBusy, save_voice_progress
from src.services.story_voice_worker import submit_story_voice_job

router = APIRouter()


class _StandardRangeFileResponse(FileResponse):
    """Delegate file transport to Starlette while standardizing its 416 header."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_standard_unsatisfied_range(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] == 416:
                headers = list(message["headers"])
                for index, (name, value) in enumerate(headers):
                    if name.lower() == b"content-range" and value.startswith(b"*/"):
                        headers[index] = (name, b"bytes " + value)
                        message = {**message, "headers": headers}
                        break
            await send(message)

        await super().__call__(scope, receive, send_with_standard_unsatisfied_range)


def get_service(db: Session) -> StoryVoiceReadingService:
    return StoryVoiceReadingService(StoryVoiceReadingRepository(db))


@router.get("/settings", response_model=VoiceReadingSettingsResponse)
def get_voice_reading_settings(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> VoiceReadingSettingsResponse:
    return get_service(db).get_settings(user_id)


@router.patch("/settings", response_model=VoiceReadingSettingsResponse)
def update_voice_reading_settings(
    request: VoiceReadingSettingsUpdateRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> VoiceReadingSettingsResponse:
    service = get_service(db)
    response = service.update_settings(
        user_id=user_id,
        selected_voice_color=request.selected_voice_color,
        auto_read_enabled=request.auto_read_enabled,
        selected_speed=request.selected_speed,
    )
    db.commit()
    return response


@router.post("/preview", response_model=VoicePreviewResponse)
def preview_voice(
    request: VoicePreviewRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> VoicePreviewResponse:
    service = get_service(db)
    result = service.preview_voice(request.voice_id)
    # Preview bytes can be cached physically, but each listener gets an owned
    # asset record so the same authenticated audio route serves all playback.
    existing = db.query(GeneratedVoiceAsset).filter_by(
        user_id=user_id, storage_path=result["audio_url"], status="ready"
    ).first()
    if existing is None:
        metadata = service.provider.metadata()
        StoryVoiceReadingRepository(db).create_asset(
            user_id=user_id, context={"source_type": "voice_preview", "text_hash": "preview:" + result["voice_id"]},
            voice_id=result["voice_id"], speed=1.0, provider=metadata.provider, model=metadata.model,
            storage_path=result["audio_url"], duration_ms=result["duration_ms"], status="ready",
        )
        db.commit()
    return VoicePreviewResponse(**result)


@router.post("/read", response_model=StoryVoiceReadingResponse)
def request_story_reading(
    request: StoryVoiceReadingRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> StoryVoiceReadingResponse:
    job_id: Optional[int] = None
    try:
        response = get_service(db).request_reading(user_id, request)
        job_id = response.job_id
        db.commit()
    except Exception as error:
        # Log independently of the failed transaction. A generated ID alone
        # must never be reported as a durably enqueued task.
        emit_diagnostic(
            "voice_job_enqueue_failed", phase="enqueue", outcome="failure", error=error,
            user_id=user_id, game_id=request.context.game_id, job_id=job_id,
            job_type="voice", persisted=False,
        )
        try:
            db.rollback()
        except Exception as rollback_error:
            emit_diagnostic(
                "voice_job_enqueue_rollback_failed", phase="rollback", outcome="failure",
                error=rollback_error, user_id=user_id, game_id=request.context.game_id,
                job_id=job_id, job_type="voice", persisted=False,
            )
        raise
    # Keep the originating HTTP request/operation identity here. The worker
    # uses a stable voice:<job_id> operation after restart; job_id joins both.
    emit_diagnostic(
        "voice_job_enqueued", phase="enqueue", outcome="success", user_id=user_id,
        game_id=request.context.game_id, job_id=response.job_id, job_type="voice",
        status=response.status, persisted=True,
    )
    if response.status == "queued":
        background_tasks.add_task(process_story_voice_job, user_id, response.job_id)
    return response


def process_story_voice_job(user_id: int, job_id: int) -> None:
    # Admission is bounded by the voice worker; excess queued work is durable
    # and discovered by its recovery scanner rather than a growing Future queue.
    submit_story_voice_job(user_id, job_id)


@router.get("/jobs/{job_id}", response_model=VoiceReadingJobResponse)
def get_voice_reading_job(
    job_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> VoiceReadingJobResponse:
    return get_service(db).get_job(user_id, job_id)


def _progress_response(progress: object) -> VoiceReadingProgressResponse:
    return VoiceReadingProgressResponse(
        game_id=int(getattr(progress, "game_id")),
        day_index=int(getattr(progress, "day_index")),
        story_date=(
            str(getattr(progress, "story_date"))
            if getattr(progress, "story_date") is not None
            else None
        ),
        text_hash=str(getattr(progress, "text_hash")),
        voice_id=str(getattr(progress, "voice_id")),
        speed=float(getattr(progress, "speed")),
        paragraph_index=int(getattr(progress, "paragraph_index")),
        position_ms=int(getattr(progress, "position_ms")),
        completed=bool(getattr(progress, "completed")),
        updated_at=(
            getattr(progress, "updated_at").isoformat()
            if getattr(progress, "updated_at") is not None
            else None
        ),
    )


@router.get("/progress", response_model=VoiceReadingProgressResponse)
def get_voice_reading_progress(
    game_id: int,
    day_index: int,
    text_hash: str,
    voice_id: str,
    speed: float = 1.0,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> VoiceReadingProgressResponse:
    progress = StoryVoiceReadingRepository(db).get_progress(
        user_id, game_id, day_index, text_hash, voice_id, speed
    )
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Progress not found")
    return _progress_response(progress)


@router.patch("/progress", response_model=VoiceReadingProgressResponse)
def update_voice_reading_progress(
    request: VoiceReadingProgressRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> VoiceReadingProgressResponse:
    try:
        progress = save_voice_progress(
            db,
            user_id=user_id,
            game_id=request.game_id,
            day_index=request.day_index,
            story_date=request.story_date,
            text_hash=request.text_hash,
            voice_id=request.voice_id,
            speed=request.speed,
            paragraph_index=request.paragraph_index,
            position_ms=request.position_ms,
            completed=request.completed,
        )
    except ProgressStoreBusy as error:
        emit_diagnostic("voice_progress", phase="persistence", outcome="failure", error=error,
                        user_id=user_id, game_id=request.game_id, error_code="progress_store_busy", retryable=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "progress_store_busy", "message": "Progress will be retried"},
            headers={"Retry-After": "1"},
        ) from error
    return _progress_response(progress)


@router.get("/audio/{file_name}")
def get_voice_reading_audio(
    file_name: str, user_id: int = Depends(get_current_user), db: Session = Depends(get_session)
) -> Response:
    storage_path = f"/api/voice-reading/audio/{file_name}"
    owned = db.query(GeneratedVoiceAsset).filter_by(
        user_id=user_id, storage_path=storage_path, status="ready"
    ).first()
    if owned is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    if not (file_name.endswith(".wav") or file_name.endswith(".mp3")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    generated_audio_path = generated_voice_file_path(file_name)
    if generated_audio_path is not None:
        media_type = "audio/mpeg" if file_name.endswith(".mp3") else "audio/wav"
        return _StandardRangeFileResponse(
            path=generated_audio_path,
            media_type=media_type,
            headers={"Cache-Control": "private, no-store", "Vary": "Cookie, Authorization"},
        )
    if not build_minimax_config().local_audio_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    if not file_name.endswith(".wav"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    stem = file_name[:-4]
    marker = "-"
    if marker not in stem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    text_hash, voice_id = stem.rsplit(marker, 1)
    if not text_hash or not voice_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    # This synchronous route runs in FastAPI's thread pool, keeping database
    # reads and deterministic fixture synthesis off the ASGI event loop.
    wav_content = build_deterministic_wav(text_hash, voice_id)
    return Response(
        content=wav_content,
        media_type="audio/wav",
        headers={"Cache-Control": "private, no-store", "Vary": "Cookie, Authorization"},
    )


@router.post("/upload-consent", response_model=MessageResponse)
async def upload_voice_consent(
    request: VoiceUploadConsentRequest,
    user_id: int = Depends(get_current_user),
) -> MessageResponse:
    if not request.consent_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
