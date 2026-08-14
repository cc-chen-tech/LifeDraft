"""Summary and ending endpoints.

This module provides endpoints for:
- GET /{game_id}/state: Get current game state
- POST /{game_id}/summary: Generate game summary
- GET /{game_id}/ending: Evaluate and return game ending
- DELETE /{game_id}/session-debug: Debug endpoint for session testing
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from config.settings import settings
from src.ai.narrative.style_manifest import get_style
from src.api.deps import get_current_user_optional, get_db
from src.api.schemas import GameStateResponse, GenerateSummaryRequest
from src.api.services.session_service import session_service
from src.api.session_store import session_store
from src.game.endings import EndingEvaluator
from src.services.life_summary_grounding import (
    build_grounded_fallback,
    build_life_summary_prompt,
    validate_or_fallback_life_summary,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_session(game_id: int, user_id: Optional[int]):
    """Get a session, auto-restoring from database if not in memory."""
    return session_service.get_or_restore(game_id, user_id)


# Debug endpoint: for testing session expiry scenarios
@router.delete("/{game_id}/session-debug")
async def clear_session_for_debug(
    game_id: int,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Debug: Clear session for specified game, simulating session expiry."""
    session_store.remove(game_id, user_id)
    logger.debug(f"Cleared session for game_id={game_id}, user_id={user_id}")
    return {"message": f"Session cleared for game {game_id}"}


@router.get("/{game_id}/state", response_model=GameStateResponse)
async def get_game_state(
    game_id: int,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Get current game state, progress, and round info."""
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop

    player_state = game_loop.player_state.to_dict() if game_loop.player_state else {}

    # Build progress info
    progress = {
        "age": player_state.get("age", 0),
        "week": player_state.get("week", 0),
        "year": player_state.get("year", 0),
    }

    # Build round info
    # current_round lives on player_state, not game_loop directly
    round_info = {
        "current_round": player_state.get("current_round", 0),
        "game_over": game_loop.is_game_over(),
    }

    # Get current event if exists
    # ★ 关键修复：不再主动从 round_history 恢复故事
    # 原因：前端在 result 阶段已经有完整故事（原故事+续写），不应该被旧故事覆盖
    # 故事恢复应该只在特定场景下进行（如页面刷新后重新加载）
    current_event = None
    logger.info(
        f"[GetGameState] game_loop.current_event exists: {game_loop.current_event is not None}"
    )
    if game_loop.current_event:
        current_event = (
            game_loop.current_event.model_dump()
            if hasattr(game_loop.current_event, "model_dump")
            else game_loop.current_event
        )
        logger.info(
            f"[GetGameState] Returning current_event with options count: {len(current_event.get('options', []))}"
        )
    else:
        logger.info("[GetGameState] No current_event, returning None")

    _raw_quality_level = getattr(game_loop, "quality_level", None)
    constraint_level = _raw_quality_level if isinstance(_raw_quality_level, str) else "expert"

    # Include narrative style in player_state for frontend access
    _raw_style_id = getattr(game_loop, "narrative_style_id", None)
    narrative_style_id = _raw_style_id if isinstance(_raw_style_id, str) else None
    if narrative_style_id:
        player_state["narrative_style_id"] = narrative_style_id

    # Get narrative style name
    narrative_style_name = None
    if narrative_style_id:
        style = get_style(narrative_style_id)
        if style:
            narrative_style_name = style.style_name

    return GameStateResponse(
        game_id=game_id,
        player_state=player_state,
        progress=progress,
        round_info=round_info,
        current_event=current_event,
        timeline=player_state.get("timeline"),
        constraint_level=constraint_level,
        narrative_style_id=narrative_style_id,
        narrative_style_name=narrative_style_name,
    )


@router.post("/{game_id}/summary")
async def generate_summary(
    game_id: int,
    req: GenerateSummaryRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Generate life summary based on complete story history."""
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop
    player = game_loop.player_state

    try:
        # ★ 优先从 player_state.round_history 获取故事（内存中的完整数据）
        # round_history 包含完整的事件描述和故事续写
        story_history = []

        if player and hasattr(player, "round_history") and player.round_history:
            for round_record in player.round_history:
                week = round_record.get("week", 0)
                round_num = round_record.get("round", 0)
                event_desc = round_record.get("event_description", "")
                story_cont = round_record.get("story_continuation", "")
                choice = round_record.get("choice", "")

                # 组合完整故事文本
                full_story_text = event_desc
                if story_cont:
                    full_story_text += "\n" + story_cont

                if full_story_text or choice:
                    story_history.append(
                        {
                            "week": week,
                            "round": round_num,
                            "story_text": full_story_text,
                            "choice_text": choice,
                        }
                    )

        # 如果 round_history 为空，尝试从 decision_history 获取
        if (
            not story_history
            and player
            and hasattr(player, "decision_history")
            and player.decision_history
        ):
            for decision in player.decision_history:
                story_history.append(
                    {
                        "week": decision.get("week", 0),
                        "story_text": decision.get("event", ""),
                        "choice_text": decision.get("choice", ""),
                    }
                )

        if not story_history:
            return {
                "start_week": 1,
                "end_week": (player.week + 1) if player else 1,
                "summary_text": "你的人生故事刚刚开始，还没有足够的经历可以总结。",
            }

        # ★ 如果前端传了 weeks 参数，只取最近 N 周的数据
        if req.weeks:
            all_weeks = sorted(set(item.get("week", 0) for item in story_history))
            if len(all_weeks) > req.weeks:
                # 只保留最近 N 周的数据
                recent_weeks = set(all_weeks[-req.weeks :])
                story_history = [
                    item for item in story_history if item.get("week", 0) in recent_weeks
                ]

        all_week_values = [item.get("week", 0) for item in story_history]
        min_week = min(all_week_values)
        max_week = max(all_week_values)
        start_week = min_week + 1
        end_week = max_week + 1
        prompt = build_life_summary_prompt(story_history, start_week, end_week)

        try:
            # P2-性能修复：人生总结是同步 LLM 调用，移到线程执行避免阻塞事件循环。
            summary_text = await asyncio.to_thread(
                game_loop.ai_generator.generate_completion,
                prompt=prompt,
                system_prompt="你是一位优秀的人生故事记录者。请为这段人生经历生成一段贴切、真实的总结。只返回总结文本，不要标题。",
                temperature=0.8,
                max_tokens=1200,
                request_timeout=settings.LIFE_SUMMARY_TIMEOUT_SECONDS,
            )
        except Exception as e:
            logger.warning(f"AI summary generation failed: {e}")
            summary_text = build_grounded_fallback(story_history, start_week, end_week)

        summary_text = validate_or_fallback_life_summary(
            summary_text,
            story_history,
            start_week,
            end_week,
        )

        return {
            "start_week": start_week,
            "end_week": end_week,
            "summary_text": summary_text,
            "story_count": len(story_history),
        }

    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _generate_fallback_summary(story_history: list, player) -> str:
    """Generate fallback summary when AI call fails."""
    if not story_history:
        return "您的人生故事刚刚开始。"
    _ = player
    weeks = [item.get("week", 0) for item in story_history]
    return build_grounded_fallback(story_history, min(weeks) + 1, max(weeks) + 1)


@router.get("/{game_id}/ending")
async def get_ending(
    game_id: int,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Evaluate and return the game ending."""
    session = _require_session(game_id, user_id)
    game_loop = session.game_loop

    if not game_loop.is_game_over():
        raise HTTPException(status_code=400, detail="Game is not over yet")

    evaluator = EndingEvaluator(ai_generator=game_loop.ai_generator)
    ending_data = evaluator.evaluate_ending(game_loop.get_state(), session.language)

    # Save ending to database
    db = get_db()
    try:
        # Merge life_review and achievements into final_state for persistence
        final_state = dict(ending_data["final_stats"])
        final_state["life_review"] = ending_data.get("life_review")
        final_state["achievements"] = ending_data.get("achievements")
        db.save_ending(
            game_id,
            final_state,
            ending_data["ending_type"],
            ending_data["summary"],
            ending_data.get("achievements"),
        )

        # Server session management: game ended, clear active game
        if user_id:
            db.clear_active_game(user_id)
            logger.info(f"Cleared active game for user {user_id} (game ended)")
    except Exception as e:
        logger.error(f"Failed to save ending: {e}")

    return ending_data
