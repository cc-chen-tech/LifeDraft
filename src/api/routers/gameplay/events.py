"""Event generation endpoints (SSE streaming and sync fallback).

This module provides endpoints for generating game events:
- GET /{game_id}/event: SSE streaming event generation
- POST /{game_id}/event-sync: Non-streaming fallback for mobile
"""
import asyncio
import logging
from typing import Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.deps import get_db, get_current_user_optional
from src.api.session_store import session_store
from src.api.services.session_service import session_service
from src.api.routers.gameplay.sse_helpers import (
    make_sse_event,
    stream_round_event,
    stream_round_event_with_asyncio_lock,
    return_sse_error,
    return_existing_event,
    replay_cached_then_complete,
    replay_cached_and_wait,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Per-game asyncio locks for event generation (prevents concurrent generation)
_game_locks: Dict[int, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()


async def _get_game_lock(game_id: int) -> asyncio.Lock:
    """Get or create an asyncio.Lock for a specific game."""
    async with _locks_lock:
        if game_id not in _game_locks:
            _game_locks[game_id] = asyncio.Lock()
        return _game_locks[game_id]


def _require_session(game_id: int, user_id: Optional[int]):
    """Get a session, auto-restoring from database if not in memory."""
    return session_service.get_or_restore(game_id, user_id)


@router.get("/{game_id}/event")
async def generate_event(
    game_id: int,
    request: Request,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Generate a round event via SSE streaming.
    
    Supports reconnection via Last-Event-ID header for mobile network resilience.
    """
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop
    
    # Parse Last-Event-ID for reconnection support
    last_event_id_str = request.headers.get("Last-Event-ID")
    last_event_id = int(last_event_id_str) if last_event_id_str is not None else None
    
    if last_event_id is not None:
        logger.info(f"SSE reconnection detected for game_id={game_id}, last_event_id={last_event_id}")

    if game_loop.is_game_over():
        raise HTTPException(status_code=400, detail="Game is already over")

    # CRITICAL: Check if we already have a valid event with options
    # This prevents re-generation when SSE connection drops and reconnects
    if game_loop.current_event and game_loop.current_event.options:
        logger.info(f"Returning existing event for game_id={game_id} (options count: {len(game_loop.current_event.options)})")
        # If reconnecting, replay cached chunks first then send complete
        if last_event_id is not None and session.sse_cache:
            return StreamingResponse(
                replay_cached_then_complete(session, last_event_id, game_loop.current_event),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )
        return StreamingResponse(
            return_existing_event(game_loop.current_event),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # CRITICAL: Check if generation is already in progress (game_loop level flag)
    # ★ 添加超时检测：如果 _generating 超过 60 秒，强制重置
    if game_loop._generating:
        # Check timeout
        if game_loop._generating_start_time:
            import time
            elapsed = time.time() - game_loop._generating_start_time
            if elapsed > 60:  # Same as GENERATION_TIMEOUT
                logger.warning(f"[event] Generation flag stuck for {elapsed:.1f}s, force reset")
                game_loop._generating = False
                game_loop._generating_start_time = None
            else:
                logger.warning(f"Event generation already in progress for game_id={game_id} (game_loop flag, {elapsed:.1f}s elapsed), returning wait message")
        else:
            # _generating_start_time 为 None 但 _generating 为 True，状态不一致，强制重置
            logger.warning(f"[event] Generation flag stuck (no timestamp), force reset for game_id={game_id}")
            game_loop._generating = False
            game_loop._generating_start_time = None
        
        # If still generating after timeout check, return error
        if game_loop._generating:
            # If reconnecting during generation, replay cached chunks
            if last_event_id is not None and session.sse_cache:
                return StreamingResponse(
                    replay_cached_and_wait(session, last_event_id),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
                )
            return StreamingResponse(
                return_sse_error("Event generation in progress, please wait"),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

    # Use asyncio.Lock to properly prevent concurrent generation in async context
    lock = await _get_game_lock(game_id)
    
    # Try to acquire lock without blocking
    if lock.locked():
        logger.warning(f"Event generation already in progress for game_id={game_id}, returning current event")
        # Return current event if exists, otherwise return error in SSE format
        if game_loop.current_event:
            return StreamingResponse(
                return_existing_event(game_loop.current_event),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )
        # If reconnecting during generation, replay cached chunks
        if last_event_id is not None and session.sse_cache:
            return StreamingResponse(
                replay_cached_and_wait(session, last_event_id),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )
        # Return error in SSE format instead of HTTPException
        return StreamingResponse(
            return_sse_error("Event generation already in progress, please wait"),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # Clear cache before starting new generation (but NOT if reconnecting)
    if last_event_id is None:
        session.clear_sse_cache()
    
    # Acquire lock before returning StreamingResponse
    await lock.acquire()
    
    return StreamingResponse(
        stream_round_event_with_asyncio_lock(game_loop, game_id, lock, session, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{game_id}/event-sync")
async def generate_event_sync(
    game_id: int,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Generate a round event (non-streaming fallback for mobile)."""
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop

    if game_loop.is_game_over():
        raise HTTPException(status_code=400, detail="Game is already over")

    # CRITICAL: Check if we already have a valid event with options
    if game_loop.current_event and game_loop.current_event.options:
        logger.info(f"Returning existing event for game_id={game_id} (sync, options count: {len(game_loop.current_event.options)})")
        return game_loop.current_event.model_dump()

    # CRITICAL: Check if generation is already in progress (game_loop level flag)
    if game_loop._generating:
        logger.warning(f"Event generation already in progress for game_id={game_id} (sync, game_loop flag)")
        raise HTTPException(status_code=409, detail="Event generation in progress, please wait")

    # Use asyncio.Lock to properly prevent concurrent generation
    lock = await _get_game_lock(game_id)
    
    if lock.locked():
        logger.warning(f"Event generation already in progress for game_id={game_id} (sync), returning current event")
        # Return current event if exists
        if game_loop.current_event:
            return game_loop.current_event.model_dump()
        raise HTTPException(status_code=409, detail="Event generation already in progress")

    async with lock:
        # Run in thread pool to avoid blocking
        loop = asyncio.get_running_loop()
        
        def run():
            return game_loop.generate_round_event()
        
        event = await loop.run_in_executor(None, run)
        
        if event is None:
            return {"event_description": "", "options": [], "game_over": game_loop.is_game_over()}
        
        return event.model_dump()
