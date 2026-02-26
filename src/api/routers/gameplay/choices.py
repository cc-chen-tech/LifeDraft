"""Choice processing endpoints (SSE streaming and sync fallback).

This module provides endpoints for processing player choices:
- POST /{game_id}/choice: SSE streaming choice processing
- POST /{game_id}/custom-choice: SSE streaming custom choice
- POST /{game_id}/choice-sync: Non-streaming fallback for mobile
- POST /{game_id}/custom-choice-sync: Non-streaming custom choice fallback
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.deps import get_db, get_current_user_optional
from src.api.session_store import session_store
from src.api.services.session_service import session_service
from src.api.schemas import MakeChoiceRequest, CustomChoiceRequest
from src.api.routers.gameplay.sse_helpers import stream_choice

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_session(game_id: int, user_id: Optional[int]):
    """Get a session, auto-restoring from database if not in memory."""
    return session_service.get_or_restore(game_id, user_id)


def _restore_current_event_if_needed(game_loop, game_id: int, user_id: Optional[int]) -> bool:
    """Restore current_event from database if it's None.
    
    Returns:
        True if event was restored or already exists, False if restoration failed.
    
    Raises:
        HTTPException: If no event can be found or restored.
    """
    if game_loop.current_event is not None:
        return True
    
    logger.warning(f"current_event is None for game_id={game_id}, attempting to restore from database")
    try:
        db = get_db()
        state_data = db.load_saved_game(game_id, user_id)
        if state_data and state_data.get("current_event_data"):
            from src.ai.models import GameEvent
            game_loop.current_event = GameEvent(**state_data["current_event_data"])
            game_loop.player_state.current_event_data = state_data["current_event_data"]
            logger.info(f"Restored current_event from database for game_id={game_id}")
            return True
        
        # If no current_event_data, check if there are recent choice records
        # This means the choice was already processed
        round_history = state_data.get("round_history", []) if state_data else []
        if round_history:
            logger.info(f"No current_event but found {len(round_history)} round records for game_id={game_id}, choice likely already processed")
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "choice_already_processed",
                    "message": "Choice was already processed. Please continue to next round."
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore current_event: {e}")
    
    raise HTTPException(status_code=400, detail="No current event. Generate an event first.")


@router.post("/{game_id}/choice")
async def make_choice(
    game_id: int,
    req: MakeChoiceRequest,
    request: Request,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Process a player choice via SSE streaming (story continuation + post-processing).
    
    Supports reconnection via Last-Event-ID header for mobile network resilience.
    """
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop
    
    # Parse Last-Event-ID for reconnection support
    last_event_id_str = request.headers.get("Last-Event-ID")
    last_event_id = int(last_event_id_str) if last_event_id_str is not None else None
    
    if last_event_id is not None:
        logger.info(f"SSE reconnection detected for choice, game_id={game_id}, last_event_id={last_event_id}")

    # Restore current_event from database if needed
    _restore_current_event_if_needed(game_loop, game_id, user_id)

    if req.option_index >= len(game_loop.current_event.options):
        raise HTTPException(status_code=400, detail="Invalid option index")

    # Clear cache before starting new choice processing (unless reconnecting)
    if last_event_id is None:
        session.clear_sse_cache()

    return StreamingResponse(
        stream_choice(game_loop, req.option_index, game_id, session, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{game_id}/custom-choice")
async def make_custom_choice(
    game_id: int,
    req: CustomChoiceRequest,
    request: Request,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Process a custom player choice via SSE streaming.
    
    Supports reconnection via Last-Event-ID header for mobile network resilience.
    """
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop
    
    # Parse Last-Event-ID for reconnection support
    last_event_id_str = request.headers.get("Last-Event-ID")
    last_event_id = int(last_event_id_str) if last_event_id_str is not None else None
    
    if last_event_id is not None:
        logger.info(f"SSE reconnection detected for custom choice, game_id={game_id}, last_event_id={last_event_id}")

    # Restore current_event from database if needed
    _restore_current_event_if_needed(game_loop, game_id, user_id)

    # Clear cache before starting new choice processing (unless reconnecting)
    if last_event_id is None:
        session.clear_sse_cache()

    return StreamingResponse(
        stream_choice(game_loop, 0, game_id, session, last_event_id, is_custom=True, custom_text=req.custom_text),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{game_id}/choice-sync")
async def make_choice_sync(
    game_id: int,
    req: MakeChoiceRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Process a player choice (non-streaming fallback for mobile)."""
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop

    # Restore current_event from database if needed
    _restore_current_event_if_needed(game_loop, game_id, user_id)

    if req.option_index >= len(game_loop.current_event.options):
        raise HTTPException(status_code=400, detail="Invalid option index")

    # Run in thread pool to avoid blocking
    loop = asyncio.get_running_loop()
    
    def run():
        return game_loop.make_round_choice(option_index=req.option_index)
    
    result = await loop.run_in_executor(None, run)
    
    # Auto-save after choice to persist current_event_data=None
    try:
        db = get_db()
        state = game_loop.get_state()
        if state:
            db.save_game_progress(game_id, state)
            logger.info(f"Auto-saved game state after sync choice: game_id={game_id}")
    except Exception as e:
        logger.warning(f"Auto-save failed after sync choice: {e}")
    
    return result


@router.post("/{game_id}/custom-choice-sync")
async def make_custom_choice_sync(
    game_id: int,
    req: CustomChoiceRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Process a custom player choice (non-streaming fallback for mobile)."""
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop

    # Restore current_event from database if needed
    _restore_current_event_if_needed(game_loop, game_id, user_id)

    # Run in thread pool to avoid blocking
    loop = asyncio.get_running_loop()
    
    def run():
        return game_loop.make_custom_choice(custom_text=req.custom_text)
    
    result = await loop.run_in_executor(None, run)
    
    # Auto-save after custom choice to persist current_event_data=None
    try:
        db = get_db()
        state = game_loop.get_state()
        if state:
            db.save_game_progress(game_id, state)
            logger.info(f"Auto-saved game state after sync custom choice: game_id={game_id}")
    except Exception as e:
        logger.warning(f"Auto-save failed after sync custom choice: {e}")
    
    return result
