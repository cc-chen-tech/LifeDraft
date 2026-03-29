"""Story adjustment router — rewrite segment, regenerate full story, assistant chat."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.deps import get_current_user_optional
from src.api.routers.gameplay.sse_helpers import (return_sse_error,
                                                  stream_regenerate,
                                                  stream_rewrite)
from src.api.schemas import (RegenerateStoryRequest, RewriteStoryRequest,
                             StoryChatRequest, StoryChatResponse)
from src.api.services.session_service import session_service
from src.api.session_store import session_store

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_session(game_id: int, user_id: Optional[int]):
    """Get a session, auto-restoring from database if not in memory."""
    return session_service.get_or_restore(game_id, user_id)


@router.post("/{game_id}/rewrite")
async def rewrite_story(
    game_id: int,
    req: RewriteStoryRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Partially rewrite a segment of the current story.

    ★ 使用前端传来的 full_story，不强制依赖 current_event
    """
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop

    try:
        # Get story context from recent rounds
        story_context = ""
        if game_loop.player_state and game_loop.player_state.round_history:
            recent_rounds = game_loop.player_state.round_history[-5:]
            story_context = "\n".join([r.get("summary", "") for r in recent_rounds])

        rewritten_story = game_loop.ai_generator.rewrite_story_segment(
            full_story=req.full_story,
            segment_to_replace=req.segment_to_replace or req.full_story,  # 未选择段落时改写整个故事
            user_instruction=req.user_instruction,
            character_settings=(
                game_loop.player_state.character_settings if game_loop.player_state else {}
            ),
            story_context=story_context,
            language=req.language,
        )

        # Update the current event description if exists
        if game_loop.current_event:
            game_loop.current_event.event_description = rewritten_story

        return {
            "new_story": rewritten_story,
            "rewritten_story": rewritten_story,
            "event": (game_loop.current_event.model_dump() if game_loop.current_event else None),
        }
    except Exception as e:
        logger.error(f"Story rewrite failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{game_id}/regenerate")
async def regenerate_story(
    game_id: int,
    req: RegenerateStoryRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Regenerate the entire current story and generate new options (non-streaming).

    ★ 现在使用完整的 generate_round_event 流程，
    确保一致性校验、关系事件、世界模型等都正常工作。
    """
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop

    # ★ 移除 current_event 检查，因为重新生成可以在任何状态下工作
    # 即使没有 current_event，也可以生成新事件

    try:
        # ★ 重置生成标志位，防止并发检查失败
        # （用户可能在之前生成未完成时点击重新生成）
        if hasattr(game_loop, "_event_generator_service"):
            game_loop._event_generator_service._generating = False
            game_loop._event_generator_service._generating_start_time = None

        # ★ 清空当前事件，让 generate_round_event 生成全新事件
        # 这确保使用完整流程：人物引入、历史摘要、关系事件、世界模型等
        game_loop.current_event = None
        if game_loop.player_state:
            game_loop.player_state.current_event_data = None

        # ★ 使用完整的 generate_round_event 流程
        new_event = game_loop.generate_round_event(
            stream_callback=None,
            status_callback=None,
        )

        if not new_event:
            raise HTTPException(status_code=500, detail="Failed to generate new event")

        return {
            "new_story": new_event.event_description,
            "event": new_event.model_dump(),
        }
    except Exception as e:
        logger.error(f"Story regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{game_id}/rewrite-stream")
async def rewrite_story_stream(
    game_id: int,
    req: RewriteStoryRequest,
    request: Request,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Rewrite story segment via SSE streaming.

    流式改写故事段落，实时输出改写结果。

    Yields:
        - status: rewrite progress
        - story: streamed story chunks
        - complete: final rewritten story
    """
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop

    # Parse Last-Event-ID for reconnection support
    last_event_id_str = request.headers.get("Last-Event-ID")
    last_event_id = int(last_event_id_str) if last_event_id_str is not None else None

    # Clear cache before starting rewrite
    if last_event_id is None:
        session.clear_sse_cache()

    return StreamingResponse(
        stream_rewrite(
            game_loop=game_loop,
            game_id=game_id,
            full_story=req.full_story,
            segment_to_replace=req.segment_to_replace or req.full_story,
            user_instruction=req.user_instruction,
            language=req.language,
            session=session,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{game_id}/regenerate-stream")
async def regenerate_story_stream(
    game_id: int,
    request: Request,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Regenerate the entire current story via SSE streaming.

    ★ 现在使用完整的 generate_round_event 流程，
    确保一致性校验、关系事件、世界模型等都正常工作。

    Yields:
        - status: regeneration progress
        - story: streamed story chunks
        - complete: final event with options
    """
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop

    # Parse Last-Event-ID for reconnection support
    last_event_id_str = request.headers.get("Last-Event-ID")
    last_event_id = int(last_event_id_str) if last_event_id_str is not None else None

    # ★ 移除 current_event 检查，因为重新生成可以在任何状态下工作
    # 即使没有 current_event，也可以生成新事件

    # Clear cache before starting regeneration
    if last_event_id is None:
        session.clear_sse_cache()

    return StreamingResponse(
        stream_regenerate(game_loop, game_id, session, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{game_id}/chat", response_model=StoryChatResponse)
async def story_assistant_chat(
    game_id: int,
    req: StoryChatRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Ask the story assistant a question about the game world, characters, etc."""
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop

    # Build context
    character_settings: dict[str, Any] = {}
    current_story = "暂无"
    if game_loop.player_state:
        character_settings = game_loop.player_state.character_settings or {}
    if game_loop.current_event and game_loop.current_event.event_description:
        current_story = game_loop.current_event.event_description

    # Include recent history for context
    recent_context = ""
    if game_loop.player_state and game_loop.player_state.round_history:
        recent_rounds = game_loop.player_state.round_history[-3:]
        recent_context = "\n".join(
            [r.get("summary", "") for r in recent_rounds if r.get("summary")]
        )

    if req.language == "zh":
        system_prompt = f"""你是一个游戏剧情助手。基于以下角色设定和当前故事，回答玩家的问题。

角色设定：{character_settings}
当前故事：{current_story}
最近经历：{recent_context or '无'}

要求：简洁、有帮助、不剧透未来发展。用中文回答。"""
    else:
        system_prompt = f"""You are a story assistant. Answer player questions based on character settings and current story.

Character Settings: {character_settings}
Current Story: {current_story}
Recent History: {recent_context or 'None'}

Requirements: Be concise, helpful, and don't spoil future developments."""

    try:
        reply = game_loop.ai_generator.generate_completion(
            prompt=req.message,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=4096,
        )
        return StoryChatResponse(reply=reply)
    except Exception as e:
        logger.error(f"Story chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
