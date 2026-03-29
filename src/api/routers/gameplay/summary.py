"""Summary and ending endpoints.

This module provides endpoints for:
- GET /{game_id}/state: Get current game state
- POST /{game_id}/summary: Generate game summary
- GET /{game_id}/ending: Evaluate and return game ending
- DELETE /{game_id}/session-debug: Debug endpoint for session testing
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user_optional, get_db
from src.api.schemas import GameStateResponse, GenerateSummaryRequest
from src.api.services.session_service import session_service
from src.api.session_store import session_store
from src.game.endings import EndingEvaluator

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
    logger.info(f"[DEBUG] Cleared session for game_id={game_id}, user_id={user_id}")
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
    round_info = {
        "current_round": (
            game_loop.current_round if hasattr(game_loop, "current_round") else 0
        ),
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

    return GameStateResponse(
        game_id=game_id,
        player_state=player_state,
        progress=progress,
        round_info=round_info,
        current_event=current_event,
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
                "end_week": player.week if player else 1,
                "summary_text": "你的人生故事刚刚开始，还没有足够的经历可以总结。",
            }

        # Build story text
        story_parts = []
        for item in story_history:
            week = item.get("week", 0)
            round_num = item.get("round", None)
            story_text = item.get("story_text", "")
            choice_text = item.get("choice_text", "")

            if story_text:
                # 包含轮次信息（如果有）
                if round_num is not None:
                    round_names = ["周一", "周中", "周末"]
                    round_name = (
                        round_names[round_num]
                        if round_num < len(round_names)
                        else f"第{round_num+1}轮"
                    )
                    story_parts.append(f"【第{week}周·{round_name}】{story_text}")
                else:
                    story_parts.append(f"【第{week}周】{story_text}")
                if choice_text:
                    story_parts.append(f"→ 选择：{choice_text}")

        full_story = "\n\n".join(story_parts)

        # Get current state
        current_state = ""
        if player:
            current_state = f"""
当前状态：
- 姓名：{player.player_name}
- 年龄：{player.age}岁
- 精力：{player.energy}/100
- 情绪：{player.mood}/100
- 学识：{player.knowledge}/100
- 财富：¥{player.wealth:,}
"""

        # Use AI to generate rich summary
        # ★ 不再截断故事，将所有历史传给模型进行完整总结
        prompt = f"""请为这段人生故事生成一段精彩的总结（300-500字）。

故事经历：
{full_story}

{current_state}

请生成一段生动的人生总结，包括：
1. 主要的人生经历和重要事件
2. 关键的决定和选择
3. 人物关系的变化
4. 成长和变化的轨迹
5. 当前的人生状态

请用第三人称叙述，语言生动有文学性，但不要过于浮夸。"""

        try:
            summary_text = game_loop.ai_generator.generate_completion(
                prompt=prompt,
                system_prompt="你是一位优秀的人生故事记录者。请为这段人生经历生成一段贴切、真实的总结。只返回总结文本，不要标题。",
                temperature=0.8,
                max_tokens=4096,
            )
        except Exception as e:
            logger.warning(f"AI summary generation failed: {e}")
            # Fallback: generate simple summary based on story
            summary_text = _generate_fallback_summary(story_history, player)

        return {
            "start_week": story_history[0].get("week", 1) if story_history else 1,
            "end_week": story_history[-1].get("week", 1) if story_history else 1,
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

    # Extract key events
    events = []
    for item in story_history[-5:]:  # Last 5 events
        story = item.get("story_text", "")
        if story and len(story) > 50:
            # Take first sentence as summary
            first_sentence = (
                story.split("。")[0] + "。" if "。" in story else story[:100]
            )
            events.append(first_sentence)

    summary_parts = []
    if player:
        summary_parts.append(
            f"{player.player_name}的人生旅程已经走过了{len(story_history)}段故事。"
        )
        summary_parts.append(
            f"当前{player.age}岁，拥有{player.wealth:,}的财富，学识水平{player.knowledge}/100。"
        )

    if events:
        summary_parts.append("近期经历：" + " ".join(events))

    return "\n".join(summary_parts)


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
        db.save_ending(
            game_id,
            ending_data["final_stats"],
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
