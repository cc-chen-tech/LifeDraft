"""Character creation router — generate settings, relationships, attributes, opening story."""

import asyncio
import json
import logging
import threading
import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.api.schemas import (GenerateAttributesRequest,
                             GenerateRelationshipRequest,
                             GenerateSettingRequest, OpeningStoryRequest,
                             RelationshipsSummaryRequest)
from src.game.character_creation import CharacterCreator

logger = logging.getLogger(__name__)
router = APIRouter()

# ★ 开场故事防重复缓存：{player_name: {"generating": bool, "result": str, "timestamp": float}}
_opening_story_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()


@router.post("/setting")
async def generate_setting(req: GenerateSettingRequest):
    """Generate a character setting (era, age, gender, world, family, relationships, traits, wealth)."""
    creator = CharacterCreator(language=req.language)
    try:
        result = creator.generate_setting(
            setting_type=req.setting_type,
            player_name=req.player_name,
            life_vision=req.life_vision,
            previous_settings=req.previous_settings,
            feedback=req.feedback,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to generate setting '{req.setting_type}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/relationship")
async def generate_relationship(req: GenerateRelationshipRequest):
    """Generate a single relationship person with rich attributes."""
    creator = CharacterCreator(language=req.language)
    try:
        result = creator.generate_single_relationship_person(
            player_name=req.player_name,
            life_vision=req.life_vision,
            previous_settings=req.previous_settings,
            existing_people=req.existing_people,
            person_index=req.person_index,
            total_needed=req.total_needed,
            feedback=req.feedback,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to generate relationship person: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/attributes")
async def generate_attributes(req: GenerateAttributesRequest):
    """Generate initial character attributes (energy, mood, knowledge, wealth)."""
    creator = CharacterCreator(language=req.language)
    try:
        result = creator.generate_initial_attributes(
            character_settings=req.character_settings,
            language=req.language,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to generate attributes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/opening-story")
async def generate_opening_story(req: OpeningStoryRequest):
    """Generate opening story via SSE streaming."""
    cache_key = req.player_name

    # ★ 检查是否正在生成或已有缓存
    with _cache_lock:
        cache_entry = _opening_story_cache.get(cache_key)
        if cache_entry:
            cache_age = time.time() - cache_entry.get("timestamp", 0)

            # 如果正在生成中，但超过 60 秒，认为已失效（可能客户端断开了）
            if cache_entry.get("generating"):
                if cache_age < 60:
                    logger.warning(
                        f"[opening-story] Already generating for {cache_key}, rejecting duplicate request"
                    )
                    raise HTTPException(
                        status_code=409, detail="Opening story generation in progress"
                    )
                else:
                    logger.warning(
                        f"[opening-story] Stale generating state for {cache_key}, resetting..."
                    )
                    # 继续执行，重新生成

            # 如果有缓存结果且不超过 5 分钟，直接返回
            if cache_entry.get("result") and cache_age < 300:
                logger.info(f"[opening-story] Returning cached result for {cache_key}")
                cached_text = cache_entry["result"]

                async def cached_generator():
                    yield f"event: status\ndata: {json.dumps({'phase': 'cached'}, ensure_ascii=False)}\n\n"
                    yield f"event: story\ndata: {json.dumps(cached_text, ensure_ascii=False)}\n\n"
                    yield f"event: complete\ndata: {json.dumps({'full_story': cached_text}, ensure_ascii=False)}\n\n"

                return StreamingResponse(
                    cached_generator(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )

        # 标记为正在生成
        _opening_story_cache[cache_key] = {
            "generating": True,
            "result": None,
            "timestamp": time.time(),
        }

    creator = CharacterCreator(language=req.language)

    async def stream_generator():
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()

        full_text_holder = [""]
        error_holder = [None]
        last_activity = [time.time()]

        def run():
            try:
                stream_response = creator.generate_opening_story(
                    character_settings=req.character_settings,
                    player_name=req.player_name,
                    life_vision=req.life_vision,
                )

                for chunk in stream_response:
                    if hasattr(chunk, "choices") and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, "content") and delta.content:
                            text = delta.content
                            full_text_holder[0] += text
                            last_activity[0] = time.time()
                            loop.call_soon_threadsafe(q.put_nowait, ("story", text))
                    elif isinstance(chunk, str):
                        # Fallback story
                        full_text_holder[0] = chunk
                        last_activity[0] = time.time()
                        loop.call_soon_threadsafe(q.put_nowait, ("story", chunk))
                        break
            except Exception as e:
                error_holder[0] = e
            finally:
                loop.call_soon_threadsafe(q.put_nowait, ("__done__", None))

        # Immediate status so client knows connection is alive
        yield f"event: status\ndata: {json.dumps({'phase': 'preparing'}, ensure_ascii=False)}\n\n"

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        # ★ 30秒超时（比120秒更快检测卡住），每5秒发送heartbeat保持连接
        HEARTBEAT_INTERVAL = 5.0
        QUEUE_TIMEOUT = 30.0
        next_heartbeat = time.time() + HEARTBEAT_INTERVAL

        while True:
            try:
                # 使用较短的超时以便定期发送heartbeat
                wait_time = min(QUEUE_TIMEOUT, max(0.1, next_heartbeat - time.time()))
                event_type, data = await asyncio.wait_for(q.get(), timeout=wait_time)
            except asyncio.TimeoutError:
                # 检查是否是heartbeat时间
                if time.time() >= next_heartbeat:
                    next_heartbeat = time.time() + HEARTBEAT_INTERVAL
                    yield f"event: status\ndata: {json.dumps({'phase': 'writing'}, ensure_ascii=False)}\n\n"
                    continue
                # 真正的超时
                yield f"event: error\ndata: {json.dumps({'error': 'Generation timeout'}, ensure_ascii=False)}\n\n"
                break

            if event_type == "__done__":
                break
            yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            next_heartbeat = time.time() + HEARTBEAT_INTERVAL

        # ★ 线程通常已完成，最多等0.1秒（原为5秒，导致不必要的延迟）
        thread.join(timeout=0.1)

        # ★ 更新缓存
        with _cache_lock:
            if error_holder[0] is not None:
                _opening_story_cache[cache_key] = {
                    "generating": False,
                    "result": None,
                    "timestamp": time.time(),
                }
                yield f"event: error\ndata: {json.dumps({'error': str(error_holder[0])}, ensure_ascii=False)}\n\n"
                return
            else:
                _opening_story_cache[cache_key] = {
                    "generating": False,
                    "result": full_text_holder[0],
                    "timestamp": time.time(),
                }

        # Send complete event with full text
        yield f"event: complete\ndata: {json.dumps({'full_story': full_text_holder[0]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/relationships-summary")
async def generate_relationships_summary(req: RelationshipsSummaryRequest):
    """Generate a narrative summary of all relationships."""
    creator = CharacterCreator(language=req.language)
    try:
        result = creator.generate_relationships_summary(
            player_name=req.player_name,
            life_vision=req.life_vision,
            previous_settings=req.previous_settings,
            key_people=req.key_people,
        )
        return {"relationships_description": result}
    except Exception as e:
        logger.error(f"Failed to generate relationships summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
