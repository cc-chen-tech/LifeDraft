"""Durable event generation endpoints (SSE and synchronous fallback)."""

import asyncio
import logging
import os
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.deps import get_current_user_optional, get_db
from src.api.routers.gameplay.sse_helpers import (
    get_or_start_round_event_generation,
    replay_cached_then_complete,
    return_existing_event,
    stream_round_event,
    wait_for_event_generation,
)
from src.api.services.event_generation_operation import EventGenerationConflict
from src.api.services.session_service import session_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_resume_view_acknowledged(game_loop) -> None:
    resume_view = getattr(game_loop.player_state, "resume_view", None)
    phase = resume_view.get("phase") if isinstance(resume_view, dict) else None
    if phase in {"result", "summary", "ending"}:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "saved_view_pending",
                "message": "A saved result is still awaiting explicit continuation.",
            },
        )


@router.post("/{game_id}/resume-view/acknowledge")
async def acknowledge_resume_view(
    game_id: int,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Clear an exact saved result only after the user explicitly continues."""
    session = _require_session(game_id, user_id)
    player_state = session.game_loop.player_state
    resume_view = getattr(player_state, "resume_view", None)
    phase = resume_view.get("phase") if isinstance(resume_view, dict) else None
    if phase not in {None, "result", "summary"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot acknowledge resume view in phase: {phase}",
        )

    player_state.resume_view = None
    db = get_db()
    db.save_game_progress(game_id, player_state)
    return {"acknowledged": True}


class SSEConnectionManager:
    """Bound concurrent SSE subscribers without owning generation jobs."""

    def __init__(self, max_per_user: int = 3, max_global: int = 1000):
        self.max_per_user = max_per_user
        self.max_global = max_global
        self._user_connections: dict[str, int] = {}
        self._global_count = 0
        self._lock = threading.Lock()

    def acquire(self, user_id: str) -> bool:
        with self._lock:
            if self._global_count >= self.max_global:
                return False
            user_count = self._user_connections.get(user_id, 0)
            if user_count >= self.max_per_user:
                return False
            self._user_connections[user_id] = user_count + 1
            self._global_count += 1
            return True

    def release(self, user_id: str) -> None:
        with self._lock:
            user_count = self._user_connections.get(user_id, 0)
            if user_count <= 0:
                return
            self._user_connections[user_id] = user_count - 1
            self._global_count -= 1
            if self._user_connections[user_id] == 0:
                del self._user_connections[user_id]


sse_manager = SSEConnectionManager()


def _require_session(game_id: int, user_id: Optional[int]):
    """Get a session, restoring it from persistent state when needed."""
    return session_service.get_or_restore(game_id, user_id)


def _is_api_contract_probe(request: Request) -> bool:
    """Identify unauthenticated Playwright route probes without blocking real E2E flows."""
    if os.getenv("E2E_CONTRACT_PROBE_FAST") != "1":
        return False
    user_agent = request.headers.get("user-agent", "")
    cookie_header = request.headers.get("cookie")
    return "Playwright" in user_agent and cookie_header is None


def _parse_last_event_id(request: Request) -> Optional[int]:
    value = request.headers.get("Last-Event-ID")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid Last-Event-ID") from exc


@router.get("/{game_id}/event")
async def generate_event(
    game_id: int,
    request: Request,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Subscribe to the current round's durable event-generation operation."""
    if _is_api_contract_probe(request):
        raise HTTPException(
            status_code=422,
            detail="API contract probe should not trigger event generation",
        )

    user_id_str = str(user_id) if user_id is not None else "anonymous"
    if not sse_manager.acquire(user_id_str):
        raise HTTPException(status_code=429, detail="Too many SSE connections")

    async def wrap_with_release(stream):
        try:
            async for item in stream:
                yield item
        finally:
            sse_manager.release(user_id_str)

    try:
        session = _require_session(game_id, user_id)
        game_loop = session.game_loop
        _require_resume_view_acknowledged(game_loop)
        last_event_id = _parse_last_event_id(request)

        if game_loop.is_game_over():
            raise HTTPException(status_code=400, detail="Game is already over")

        if game_loop.current_event and game_loop.current_event.options:
            if last_event_id is not None:
                stream = replay_cached_then_complete(
                    session, last_event_id, game_loop.current_event
                )
            else:
                stream = return_existing_event(game_loop.current_event)
        else:
            stream = stream_round_event(
                game_loop,
                game_id,
                session,
                last_event_id,
            )

        return StreamingResponse(
            wrap_with_release(stream),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception:
        sse_manager.release(user_id_str)
        raise


@router.post("/{game_id}/event-sync")
async def generate_event_sync(
    game_id: int,
    request: Request,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Wait for the same durable operation used by SSE subscribers."""
    if _is_api_contract_probe(request):
        raise HTTPException(
            status_code=422,
            detail="API contract probe should not trigger event generation",
        )

    session = _require_session(game_id, user_id)
    game_loop = session.game_loop
    _require_resume_view_acknowledged(game_loop)

    if game_loop.is_game_over():
        raise HTTPException(status_code=400, detail="Game is already over")

    if game_loop.current_event and game_loop.current_event.options:
        return game_loop.current_event.model_dump()

    try:
        operation, _ = get_or_start_round_event_generation(game_loop, game_id, session)
    except EventGenerationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        snapshot = await wait_for_event_generation(operation)
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Event generation is still running; reconnect to continue waiting",
        ) from exc

    if snapshot.status == "failed":
        raise HTTPException(
            status_code=503,
            detail=snapshot.error or "Event generation failed",
        )
    if snapshot.result is None:
        raise HTTPException(status_code=503, detail="Event generation returned no result")
    return snapshot.result.model_dump()
