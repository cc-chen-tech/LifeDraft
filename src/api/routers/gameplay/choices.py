"""Choice processing endpoints (SSE streaming and sync fallback).

This module provides endpoints for processing player choices:
- POST /{game_id}/choice: SSE streaming choice processing
- POST /{game_id}/custom-choice: SSE streaming custom choice
- POST /{game_id}/choice-sync: Non-streaming fallback for mobile
- POST /{game_id}/custom-choice-sync: Non-streaming custom choice fallback
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.deps import get_current_user_optional, get_db
from src.api.routers.gameplay.sse_helpers import stream_choice
from src.api.schemas import CustomChoiceRequest, MakeChoiceRequest
from src.api.services.session_service import session_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _is_choice_already_processed(exc: HTTPException) -> bool:
    detail = exc.detail
    if isinstance(detail, dict):
        return detail.get("error") == "choice_already_processed"
    return "choice_already_processed" in str(detail)


def _latest_processed_choice_result(state_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build an idempotent choice-sync response from the latest saved round."""
    round_history = state_data.get("round_history", []) if state_data else []
    if not isinstance(round_history, list) or not round_history:
        return None

    latest = round_history[-1]
    if not isinstance(latest, dict):
        return None

    story_continuation = latest.get("story_continuation")
    summary = latest.get("summary")
    if not isinstance(story_continuation, str) and not isinstance(summary, str):
        return None

    effects = latest.get("effects")
    effects_requested = latest.get("effects_requested")
    resource_warnings = latest.get("resource_warnings")

    return {
        "story_continuation": story_continuation if isinstance(story_continuation, str) else "",
        "summary": summary if isinstance(summary, str) else "",
        "effects_applied": effects if isinstance(effects, dict) else {},
        "effects_requested": effects_requested if isinstance(effects_requested, dict) else (
            effects if isinstance(effects, dict) else {}
        ),
        "resource_warnings": resource_warnings if isinstance(resource_warnings, list) else [],
        "need_weekly_summary": False,
        "weekly_summary": None,
        "game_over": bool(state_data.get("game_over", False)) if state_data else False,
    }


def _restore_latest_processed_choice_result(
    game_id: int, user_id: Optional[int]
) -> Optional[Dict[str, Any]]:
    db = get_db()
    state_data = db.load_saved_game(game_id, user_id)  # type: ignore[arg-type]
    result = _latest_processed_choice_result(state_data)
    if result is not None:
        logger.info(
            "Returning latest processed choice result for duplicate sync request: game_id=%s",
            game_id,
        )
    return result


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

    logger.warning(
        f"current_event is None for game_id={game_id}, attempting to restore from database"
    )
    try:
        db = get_db()
        state_data = db.load_saved_game(game_id, user_id)  # type: ignore[arg-type]
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
            logger.info(
                f"No current_event but found {len(round_history)} round records for game_id={game_id}, choice likely already processed"
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "choice_already_processed",
                    "message": "Choice was already processed. Please continue to next round.",
                },
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
        logger.info(
            f"SSE reconnection detected for choice, game_id={game_id}, last_event_id={last_event_id}"
        )

    # Restore current_event from database if needed
    _restore_current_event_if_needed(game_loop, game_id, user_id)

    if req.option_index >= len(game_loop.current_event.options):
        raise HTTPException(status_code=400, detail="Invalid option index")

    # Clear cache before starting new choice processing (unless reconnecting)
    if last_event_id is None:
        session.clear_sse_cache()
        session.clear_options_cache()  # ★ Clear options cache when choice is made

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
        logger.info(
            f"SSE reconnection detected for custom choice, game_id={game_id}, last_event_id={last_event_id}"
        )

    # Restore current_event from database if needed
    _restore_current_event_if_needed(game_loop, game_id, user_id)

    # Clear cache before starting new choice processing (unless reconnecting)
    if last_event_id is None:
        session.clear_sse_cache()
        session.clear_options_cache()  # ★ Clear options cache when custom choice is made

    return StreamingResponse(
        stream_choice(
            game_loop,
            0,
            game_id,
            session,
            last_event_id,
            is_custom=True,
            custom_text=req.custom_text,
        ),
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
    try:
        _restore_current_event_if_needed(game_loop, game_id, user_id)
    except HTTPException as exc:
        if user_id is not None and _is_choice_already_processed(exc):
            result = _restore_latest_processed_choice_result(game_id, user_id)
            if result is not None:
                return result
        if user_id is None and exc.status_code == 400:
            raise HTTPException(status_code=422, detail=exc.detail)
        raise

    if req.option_index >= len(game_loop.current_event.options):
        raise HTTPException(status_code=400, detail="Invalid option index")

    # Run in thread pool to avoid blocking
    loop = asyncio.get_running_loop()

    def run():
        return game_loop.make_round_choice(option_index=req.option_index)

    try:
        result = await loop.run_in_executor(None, run)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

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
    try:
        _restore_current_event_if_needed(game_loop, game_id, user_id)
    except HTTPException as exc:
        if user_id is not None and _is_choice_already_processed(exc):
            result = _restore_latest_processed_choice_result(game_id, user_id)
            if result is not None:
                return result
        if user_id is None and exc.status_code == 400:
            raise HTTPException(status_code=422, detail=exc.detail)
        raise

    # Run in thread pool to avoid blocking
    loop = asyncio.get_running_loop()

    def run():
        return game_loop.make_custom_choice(custom_text=req.custom_text)

    try:
        result = await loop.run_in_executor(None, run)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

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
