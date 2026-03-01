"""SSE streaming utilities for gameplay endpoints.

This module provides reusable SSE (Server-Sent Events) streaming functions
for event generation and choice processing.
"""
import asyncio
import json
import logging
import threading
from typing import Optional, Dict, Any, List

from src.api.deps import get_db

logger = logging.getLogger(__name__)


def _trigger_round_illustration_generation(game_loop, game_id: int, event, stage: str = "event") -> None:
    """
    异步触发每轮场景插画生成
    
    在后台线程中执行，不阻塞游戏流程
    
    Args:
        game_loop: 游戏循环实例
        game_id: 游戏ID
        event: 事件对象
        stage: 场景阶段 (event=事件故事, result=结果故事)
    """
    def generate_illustration():
        try:
            from src.game.round.illustration_service import RoundIllustrationService
            from src.ai.image_client import ImageClient
            from src.services.image_storage import ImageStorageService
            from src.database.models import Game, Image as ImageModel, SessionLocal
            
            # 创建数据库会话
            db = SessionLocal()
            
            try:
                # 获取游戏信息
                game = db.query(Game).filter(Game.game_id == game_id).first()
                if not game:
                    logger.warning(f"[RoundIllustration] Game {game_id} not found")
                    return
                
                # 获取玩家状态
                player_state = game_loop.player_state
                if not player_state:
                    logger.warning(f"[RoundIllustration] No player state for game {game_id}")
                    return

                # 获取当前轮次和周数
                round_number = player_state.current_round
                week = player_state.week  # ★ 获取周数

                # ★ 检查是否已存在该周该轮该阶段的插画
                from src.database.models import SceneImage
                existing = db.query(SceneImage).filter(
                    SceneImage.game_id == game_id,
                    SceneImage.week == week,  # ★ 加入 week 条件
                    SceneImage.round_number == round_number,
                    SceneImage.stage == stage,  # ★ 区分阶段
                ).first()
                
                if existing:
                    week_display = f"第{week + 1}周" if week is not None else "未知周"
                    logger.info(f"[RoundIllustration] {week_display} round {round_number} stage={stage} 插画已存在")
                    return

                # 获取故事文本
                story_text = event.event_description if event else ""
                if not story_text:
                    week_display = f"第{week + 1}周" if week is not None else "未知周"
                    logger.warning(f"[RoundIllustration] {week_display} round {round_number} 无故事文本")
                    return
                
                # 获取角色设定
                character_settings = player_state.character_settings or {}
                player_name = player_state.player_name or "主角"

                # 获取世界模型数据与已建立事实（用于更精确的实体/物品识别）
                world_model_data = player_state.world_model_data or {}
                established_facts = getattr(player_state, "established_facts", []) or []
                
                # 获取已有图片
                images = db.query(ImageModel).filter(
                    ImageModel.game_id == game_id,
                    ImageModel.is_active == True
                ).all()
                
                existing_images = [
                    {
                        "image_id": img.image_id,
                        "entity_name": img.entity_name,
                        "image_type": img.image_type,
                        "entity_key": img.entity_key,
                    }
                    for img in images
                ]
                
                logger.info(f"[RoundIllustration] Found {len(existing_images)} existing images for game {game_id}")
                
                # 创建服务实例
                image_client = ImageClient()
                image_storage = ImageStorageService()
                illustration_service = RoundIllustrationService(
                    image_client=image_client,
                    image_storage=image_storage,
                    db_session=db
                )
                
                # 异步生成插画
                illustration_service.generate_round_illustration_async(
                    game_id=game_id,
                    round_number=round_number,
                    story_text=story_text,
                    character_settings=character_settings,
                    player_name=player_name,
                    existing_images=existing_images,
                    stage=stage,  # ★ 传递 stage 参数
                    week=week,  # ★ 传递 week 参数
                    world_model_data=world_model_data,
                    established_facts=established_facts,
                )

                week_display = f"第{week + 1}周" if week is not None else "未知周"
                logger.info(f"[RoundIllustration] 触发异步生成: game={game_id}, {week_display}, round {round_number}, stage={stage}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"[RoundIllustration] Failed to trigger generation: {e}")
    
    # 在后台线程中执行
    thread = threading.Thread(target=generate_illustration, daemon=True)
    thread.start()


def make_sse_event(event_type: str, data, event_id: Optional[int] = None) -> str:
    """Format an SSE event string with optional event ID for reconnection support."""
    id_line = f"id: {event_id}\n" if event_id is not None else ""
    return f"{id_line}event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def clear_sse_cache_if_retry(status: dict, session) -> None:
    """Clear SSE cache when retry status is detected.
    
    This ensures that when a story is being regenerated due to consistency issues,
    the old cached chunks are removed so the frontend starts fresh.
    """
    if session is not None and status.get("phase") == "retry":
        logger.info("[SSE] Retry detected, clearing SSE cache for fresh start")
        session.clear_sse_cache()


async def stream_round_event(game_loop, game_id: int, session=None, last_event_id: Optional[int] = None):
    """
    Async generator that streams round event generation via SSE.
    Uses asyncio.Queue for zero-latency event forwarding from worker thread.
    Yields SSE events: status, story (chunks), complete (final event).
    Includes heartbeat mechanism to keep connection alive.
    Auto-saves game state after event generation to enable resume.
    
    Reconnection support:
    - session: GameLoopSession for caching story chunks
    - last_event_id: If provided, replay cached chunks first (断点续传)
    """
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()
    
    # ★ 标记连接是否已关闭，避免向已关闭的事件循环发送回调
    closed = [False]

    def stream_cb(text):
        if closed[0] or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(q.put_nowait, ("story", text))
        except RuntimeError:
            closed[0] = True  # 事件循环已关闭

    def status_cb(status):
        if closed[0] or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(q.put_nowait, ("status", {"phase": status}))
        except RuntimeError:
            closed[0] = True  # 事件循环已关闭

    result_holder = [None]
    error_holder = [None]

    def run():
        try:
            result_holder[0] = game_loop.generate_round_event(
                stream_callback=stream_cb,
                status_callback=status_cb,
            )
        except Exception as e:
            error_holder[0] = e
        finally:
            if not closed[0] and not loop.is_closed():
                try:
                    loop.call_soon_threadsafe(q.put_nowait, ("__done__", None))
                except RuntimeError:
                    pass

    # ---- Reconnection: just continue from where we left off ----
    # Frontend already has the content up to last_event_id, no need to replay
    if last_event_id is not None and session is not None:
        cached_count = len(session.sse_cache)
        if cached_count > 0:
            logger.info(f"Reconnection detected, last_event_id={last_event_id}, cached={cached_count} chunks")
            # If generation was already complete, just send complete event
            if not session._is_generating and session.sse_cache:
                event = game_loop.current_event
                if event and event.options:
                    logger.info(f"Generation already complete, sending complete event directly")
                    yield make_sse_event("status", {"phase": "resuming"})
                    yield make_sse_event("complete", event.model_dump())
                    return

    # Immediately tell the client we're alive and processing
    yield make_sse_event("status", {"phase": "preparing"})

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    # Heartbeat: send keep-alive every 5 seconds to prevent connection timeout
    heartbeat_interval = 5
    last_event_time = asyncio.get_event_loop().time()

    # Yield SSE events as they arrive — fully async, no thread pool overhead
    while True:
        try:
            # Use shorter timeout for heartbeat check
            event_type, data = await asyncio.wait_for(q.get(), timeout=heartbeat_interval)
            last_event_time = asyncio.get_event_loop().time()
        except asyncio.TimeoutError:
            # Check if overall timeout exceeded (120 seconds)
            elapsed = asyncio.get_event_loop().time() - last_event_time
            if elapsed > 120:
                yield make_sse_event("error", {"error": "Timeout waiting for event generation"})
                break
            # Send heartbeat to keep connection alive
            yield make_sse_event("status", {"phase": "processing", "heartbeat": True})
            continue

        if event_type == "__done__":
            break
        
        # ★ Handle retry status: clear cache before sending
        if event_type == "status" and isinstance(data, dict):
            clear_sse_cache_if_retry(data, session)
        
        # Cache story chunks for reconnection support
        if event_type == "story" and session is not None:
            event_id = session.cache_sse_chunk(data)
            yield make_sse_event(event_type, data, event_id=event_id)
        else:
            yield make_sse_event(event_type, data)

    thread.join(timeout=5)

    # Check for errors
    if error_holder[0] is not None:
        yield make_sse_event("error", {"error": str(error_holder[0])})
        # Clear cache on error
        if session is not None:
            session.clear_sse_cache()
        return

    # Send complete event with full event data
    event = result_holder[0]
    if event is not None:
        # Debug log: check if event_description is complete
        desc = event.event_description
        logger.info(f"[SSE Complete] event_description length: {len(desc)} chars")
        logger.info(f"[SSE Complete] Last 100 chars: ...{desc[-100:] if len(desc) > 100 else desc}")
        
        yield make_sse_event("complete", event.model_dump())
        
        # Auto-save game state after event generation
        # This ensures user can resume from this point even if they close the page
        try:
            db = get_db()
            state = game_loop.get_state()
            if state:
                db.save_game_progress(game_id, state)
                logger.info(f"Auto-saved game state after event generation: game_id={game_id}")
        except Exception as e:
            logger.warning(f"Auto-save failed after event generation: {e}")
        
        # ★ 异步触发每轮场景插画生成（不阻塞游戏流程）
        # event 阶段的插画在事件生成完成后触发
        try:
            _trigger_round_illustration_generation(game_loop, game_id, event, stage="event")
        except Exception as e:
            logger.warning(f"Failed to trigger round illustration generation: {e}")
    else:
        yield make_sse_event("complete", {"event_description": "", "options": []})
    
    # Note: Don't clear cache immediately - keep for potential reconnects
    # Cache will be cleared when new generation starts


async def stream_choice(game_loop, option_index: int, game_id: int, session=None, last_event_id: Optional[int] = None, is_custom: bool = False, custom_text: str = ""):
    """
    Async generator that streams choice processing (story continuation) via SSE.
    Uses asyncio.Queue for zero-latency event forwarding from worker thread.
    Yields SSE events: status, story (continuation chunks), complete (result).
    Includes heartbeat mechanism to keep connection alive.
    
    Reconnection support:
    - session: GameLoopSession for caching story chunks
    - last_event_id: If provided, replay cached chunks first (断点续传)
    """
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()
    
    # ★ 标记连接是否已关闭，避免向已关闭的事件循环发送回调
    closed = [False]

    def stream_cb(text):
        if closed[0] or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(q.put_nowait, ("story", text))
        except RuntimeError:
            closed[0] = True

    def status_cb(status):
        if closed[0] or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(q.put_nowait, ("status", {"phase": status}))
        except RuntimeError:
            closed[0] = True

    result_holder = [None]
    error_holder = [None]

    def run():
        try:
            if is_custom:
                result_holder[0] = game_loop.make_custom_choice(
                    custom_text=custom_text,
                    stream_callback=stream_cb,
                    status_callback=status_cb,
                )
            else:
                result_holder[0] = game_loop.make_round_choice(
                    option_index=option_index,
                    stream_callback=stream_cb,
                    status_callback=status_cb,
                )
        except Exception as e:
            error_holder[0] = e
        finally:
            if not closed[0] and not loop.is_closed():
                try:
                    loop.call_soon_threadsafe(q.put_nowait, ("__done__", None))
                except RuntimeError:
                    pass

    # ---- Reconnection: replay cached chunks if last_event_id provided ----
    if last_event_id is not None and session is not None:
        cached_chunks = session.get_cached_chunks_after(last_event_id)
        if cached_chunks:
            logger.info(f"Replaying {len(cached_chunks)} cached chunks from event_id={last_event_id + 1}")
            yield make_sse_event("status", {"phase": "replaying", "cached_count": len(cached_chunks)})
            for event_id, chunk in cached_chunks:
                yield make_sse_event("story", chunk, event_id=event_id)

    # Immediately tell the client we're alive and processing
    yield make_sse_event("status", {"phase": "preparing"})

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    # Heartbeat: send keep-alive every 5 seconds to prevent connection timeout
    heartbeat_interval = 5
    last_event_time = asyncio.get_event_loop().time()

    while True:
        try:
            event_type, data = await asyncio.wait_for(q.get(), timeout=heartbeat_interval)
            last_event_time = asyncio.get_event_loop().time()
        except asyncio.TimeoutError:
            # Check if overall timeout exceeded (120 seconds)
            elapsed = asyncio.get_event_loop().time() - last_event_time
            if elapsed > 120:
                yield make_sse_event("error", {"error": "Timeout processing choice"})
                break
            # Send heartbeat to keep connection alive
            yield make_sse_event("status", {"phase": "processing", "heartbeat": True})
            continue

        if event_type == "__done__":
            break

        # ★ Handle retry status: clear cache before sending
        if event_type == "status" and isinstance(data, dict):
            clear_sse_cache_if_retry(data, session)

        # Cache story chunks for reconnection support
        if event_type == "story" and session is not None:
            event_id = session.cache_sse_chunk(data)
            yield make_sse_event(event_type, data, event_id=event_id)
        else:
            yield make_sse_event(event_type, data)

    thread.join(timeout=5)

    if error_holder[0] is not None:
        yield make_sse_event("error", {"error": str(error_holder[0])})
        # Clear cache on error
        if session is not None:
            session.clear_sse_cache()
        return

    result = result_holder[0]
    if result is not None:
        yield make_sse_event("complete", result)
        
        # Auto-save after choice to persist current_event_data=None
        try:
            db = get_db()
            state = game_loop.get_state()
            if state:
                db.save_game_progress(game_id, state)
                logger.info(f"Auto-saved game state after choice: game_id={game_id}")
        except Exception as e:
            logger.warning(f"Auto-save failed after choice: {e}")
    else:
        yield make_sse_event("error", {"error": "No result from choice processing"})


async def return_sse_error(message: str):
    """Return error as SSE stream."""
    yield make_sse_event("error", {"error": message, "message": message})


async def return_existing_event(event):
    """Return existing event as SSE stream."""
    yield make_sse_event("complete", event.model_dump())


async def replay_cached_then_complete(session, last_event_id: int, event):
    """Send complete event for reconnection after generation finished.
    
    Frontend already has the story content, just send the complete event.
    """
    logger.info(f"Reconnection after completion, sending complete event directly (last_event_id={last_event_id})")
    yield make_sse_event("status", {"phase": "resuming"})
    yield make_sse_event("complete", event.model_dump())


async def replay_cached_and_wait(session, last_event_id: int):
    """Continue streaming for reconnection during ongoing generation.
    
    Frontend already has content up to last_event_id, just wait for new chunks.
    """
    logger.info(f"Reconnection during generation, waiting for new content (last_event_id={last_event_id})")
    current_id = last_event_id
    
    # Tell frontend we're resuming
    yield make_sse_event("status", {"phase": "resuming"})
    
    poll_count = 0
    max_polls = 120  # Max 2 minutes of polling (120 * 1s)
    
    while session._is_generating and poll_count < max_polls:
        await asyncio.sleep(1)  # Poll every 1 second
        poll_count += 1
        
        # Check for new chunks
        new_chunks = session.get_cached_chunks_after(current_id)
        if new_chunks:
            for event_id, chunk in new_chunks:
                yield make_sse_event("story", chunk, event_id=event_id)
                current_id = event_id
        
        # Send heartbeat every 5 seconds
        if poll_count % 5 == 0:
            yield make_sse_event("status", {"phase": "processing", "heartbeat": True})
    
    # Generation finished, check if we have the complete event
    game_loop = session.game_loop
    if game_loop.current_event and game_loop.current_event.options:
        # Replay any remaining chunks
        final_chunks = session.get_cached_chunks_after(current_id)
        for event_id, chunk in final_chunks:
            yield make_sse_event("story", chunk, event_id=event_id)
        # Send complete event
        yield make_sse_event("complete", game_loop.current_event.model_dump())
    else:
        # Generation timed out or failed
        yield make_sse_event("error", {"error": "Generation timed out, please try again"})


async def stream_round_event_with_asyncio_lock(game_loop, game_id: int, lock: asyncio.Lock, session=None, last_event_id: Optional[int] = None):
    """Wrapper that ensures asyncio lock is released after streaming completes."""
    try:
        async for event in stream_round_event(game_loop, game_id, session, last_event_id):
            yield event
    finally:
        lock.release()


async def stream_regenerate(game_loop, game_id: int, session=None, last_event_id: Optional[int] = None):
    """
    Async generator that streams story regeneration via SSE.
    
    ★ 统一流程：使用完整的 generate_round_event 流程，
    确保一致性校验、关系事件、世界模型等都正常工作。
    
    Yields SSE events: status, story (chunks), complete (final event).
    """
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()
    
    # ★ 标记连接是否已关闭
    closed = [False]

    def stream_cb(text):
        if closed[0] or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(q.put_nowait, ("story", text))
        except RuntimeError:
            closed[0] = True

    def status_cb(status):
        if closed[0] or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(q.put_nowait, ("status", {"phase": status}))
        except RuntimeError:
            closed[0] = True

    result_holder = [None]
    error_holder = [None]

    def run():
        try:
            # ★ 使用完整的 generate_round_event 流程
            # 这确保了一致性校验、关系事件、世界模型等都正常工作
                
            # ★ 重置生成标志位，防止并发检查失败
            # （用户可能在之前生成未完成时点击重新生成）
            if hasattr(game_loop, '_event_generator_service'):
                game_loop._event_generator_service._generating = False
                game_loop._event_generator_service._generating_start_time = None
                
            # 清空当前事件，让 generate_round_event 生成全新事件
            game_loop.current_event = None
                
            # 调用 game_loop 的完整生成流程
            new_event = game_loop.generate_round_event(
                stream_callback=stream_cb,
                status_callback=status_cb,
            )
                
            if new_event and new_event.options:
                result_holder[0] = new_event
                logger.info(f"Regeneration complete: {len(new_event.event_description)} chars, {len(new_event.options)} options")
            else:
                error_holder[0] = ValueError("Failed to generate valid event with options")
                    
        except Exception as e:
            logger.error(f"Regeneration failed: {e}")
            error_holder[0] = e
        finally:
            if not closed[0] and not loop.is_closed():
                try:
                    loop.call_soon_threadsafe(q.put_nowait, ("__done__", None))
                except RuntimeError:
                    pass

    # Tell client we're starting
    yield make_sse_event("status", {"phase": "regenerating"})

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    # Heartbeat mechanism
    heartbeat_interval = 5
    last_event_time = asyncio.get_event_loop().time()

    while True:
        try:
            event_type, data = await asyncio.wait_for(q.get(), timeout=heartbeat_interval)
            last_event_time = asyncio.get_event_loop().time()
        except asyncio.TimeoutError:
            elapsed = asyncio.get_event_loop().time() - last_event_time
            if elapsed > 120:
                yield make_sse_event("error", {"error": "Timeout during regeneration"})
                break
            yield make_sse_event("status", {"phase": "processing", "heartbeat": True})
            continue

        if event_type == "__done__":
            break

        # ★ Handle retry status: clear cache before sending
        if event_type == "status" and isinstance(data, dict):
            clear_sse_cache_if_retry(data, session)

        # Cache story chunks for reconnection support
        if event_type == "story" and session is not None:
            event_id = session.cache_sse_chunk(data)
            yield make_sse_event(event_type, data, event_id=event_id)
        else:
            yield make_sse_event(event_type, data)

    thread.join(timeout=5)

    if error_holder[0] is not None:
        yield make_sse_event("error", {"error": str(error_holder[0])})
        if session is not None:
            session.clear_sse_cache()
        return

    # Send complete event with full event data
    event = result_holder[0]
    if event is not None:
        yield make_sse_event("complete", event.model_dump())
        
        # Auto-save game state
        try:
            db = get_db()
            state = game_loop.get_state()
            if state:
                db.save_game_progress(game_id, state)
                logger.info(f"Auto-saved game state after regeneration: game_id={game_id}")
        except Exception as e:
            logger.warning(f"Auto-save failed after regeneration: {e}")
    else:
        yield make_sse_event("complete", {"event_description": "", "options": []})


async def stream_rewrite(
    game_loop,
    game_id: int,
    full_story: str,
    segment_to_replace: str,
    user_instruction: str,
    language: str = "zh",
    session=None,
):
    """
    Async generator that streams story rewriting via SSE.
    
    流式改写故事段落，支持实时输出。
    
    Yields SSE events: status, story (chunks), complete (final result).
    """
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()
    
    # ★ 标记连接是否已关闭
    closed = [False]

    def stream_cb(text):
        if closed[0] or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(q.put_nowait, ("story", text))
        except RuntimeError:
            closed[0] = True

    result_holder = [None]
    error_holder = [None]

    def status_cb(status):
        if closed[0] or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(q.put_nowait, ("status", {"phase": status}))
        except RuntimeError:
            closed[0] = True

    def run():
        try:
            # Get story context from recent rounds
            story_context = ""
            if game_loop.player_state and game_loop.player_state.round_history:
                recent_rounds = game_loop.player_state.round_history[-5:]
                story_context = "\n".join([r.get("summary", "") for r in recent_rounds])
            
            # Get character settings
            character_settings = {}
            if game_loop.player_state:
                character_settings = game_loop.player_state.character_settings or {}
            
            # ★ 获取 world_model 用于一致性校验
            world_model = None
            player_state_dict = None
            if game_loop.player_state:
                try:
                    from src.game.world_model import WorldModel
                    world_model = WorldModel.from_player_state(game_loop.player_state)
                    player_state_dict = game_loop.player_state.to_dict() if hasattr(game_loop.player_state, 'to_dict') else dict(game_loop.player_state.__dict__)
                except Exception as e:
                    logger.warning(f"[Rewrite] Failed to build WorldModel: {e}")
            
            rewritten_story = game_loop.ai_generator.rewrite_story_segment(
                full_story=full_story,
                segment_to_replace=segment_to_replace or full_story,
                user_instruction=user_instruction,
                character_settings=character_settings,
                story_context=story_context,
                language=language,
                stream_callback=stream_cb,
                status_callback=status_cb,
                world_model=world_model,
                player_state=player_state_dict,
            )
            
            if rewritten_story:
                result_holder[0] = rewritten_story
                logger.info(f"Rewrite complete: {len(rewritten_story)} chars")
            else:
                error_holder[0] = ValueError("Failed to rewrite story")
                
        except Exception as e:
            logger.error(f"Rewrite failed: {e}")
            error_holder[0] = e
        finally:
            if not closed[0] and not loop.is_closed():
                try:
                    loop.call_soon_threadsafe(q.put_nowait, ("__done__", None))
                except RuntimeError:
                    pass

    # Tell client we're starting
    yield make_sse_event("status", {"phase": "rewriting"})

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    # Heartbeat mechanism
    heartbeat_interval = 5
    last_event_time = asyncio.get_event_loop().time()

    while True:
        try:
            event_type, data = await asyncio.wait_for(q.get(), timeout=heartbeat_interval)
            last_event_time = asyncio.get_event_loop().time()
        except asyncio.TimeoutError:
            elapsed = asyncio.get_event_loop().time() - last_event_time
            if elapsed > 120:
                yield make_sse_event("error", {"error": "Timeout during rewrite"})
                break
            yield make_sse_event("status", {"phase": "processing", "heartbeat": True})
            continue

        if event_type == "__done__":
            break

        # ★ Handle retry status: clear cache before sending
        if event_type == "status" and isinstance(data, dict):
            clear_sse_cache_if_retry(data, session)

        # Cache story chunks for reconnection support
        if event_type == "story" and session is not None:
            event_id = session.cache_sse_chunk(data)
            yield make_sse_event(event_type, data, event_id=event_id)
        else:
            yield make_sse_event(event_type, data)

    thread.join(timeout=5)

    if error_holder[0] is not None:
        yield make_sse_event("error", {"error": str(error_holder[0])})
        if session is not None:
            session.clear_sse_cache()
        return

    # Send complete event with rewritten story
    rewritten_story = result_holder[0]
    if rewritten_story is not None:
        # Update the current event description if exists
        if game_loop.current_event:
            game_loop.current_event.event_description = rewritten_story
        
        yield make_sse_event("complete", {
            "new_story": rewritten_story,
            "rewritten_story": rewritten_story,
            "event": game_loop.current_event.model_dump() if game_loop.current_event else None,
        })
        
        # Clear SSE cache after successful completion
        if session is not None:
            session.clear_sse_cache()
    else:
        yield make_sse_event("complete", {"new_story": "", "rewritten_story": "", "event": None})
