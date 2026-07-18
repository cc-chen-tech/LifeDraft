"""SSE streaming utilities for gameplay endpoints.

This module provides reusable SSE (Server-Sent Events) streaming functions
for event generation and choice processing.
"""

import asyncio
import copy
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import RLock
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

from config.settings import settings
from src.api.deps import get_db
from src.api.services.event_generation_operation import (
    EventGenerationConflict,
    EventGenerationKey,
)

logger = logging.getLogger(__name__)

# SSE 流超时配置（必须小于 Nginx proxy_read_timeout）
SSE_STREAM_TIMEOUT = 330
# 心跳间隔（秒），防止 Nginx 空闲超时断连
HEARTBEAT_INTERVAL = 5

# Gameplay execution pools. Story work has a dedicated lane; optional media and
# prefetch work must never consume its workers.
_sse_thread_pool: Optional[ThreadPoolExecutor] = None
_background_thread_pool: Optional[ThreadPoolExecutor] = None
_thread_pool_lock = RLock()
_background_jobs_enabled = True


@dataclass(frozen=True)
class RoundIllustrationJob:
    """Immutable event context used by a delayed scene-generation task."""

    game_id: int
    week: int
    round_number: int
    stage: str
    story_text: str
    character_settings: Dict[str, Any]
    player_name: str
    world_model_data: Dict[str, Any]
    established_facts: List[Dict[str, Any]]


def _get_sse_thread_pool() -> ThreadPoolExecutor:
    global _sse_thread_pool
    with _thread_pool_lock:
        if _sse_thread_pool is None:
            _sse_thread_pool = ThreadPoolExecutor(max_workers=20, thread_name_prefix="sse-worker")
        return _sse_thread_pool


# Public alias for contract tests
get_sse_thread_pool = _get_sse_thread_pool


def _get_background_thread_pool() -> ThreadPoolExecutor:
    """Return the bounded pool for non-critical media and prefetch work."""
    global _background_thread_pool
    with _thread_pool_lock:
        if not _background_jobs_enabled:
            raise RuntimeError("Background jobs are disabled during application shutdown")
        if _background_thread_pool is None:
            _background_thread_pool = ThreadPoolExecutor(
                max_workers=4,
                thread_name_prefix="background-worker",
            )
        return _background_thread_pool


# Public alias for contract tests
get_background_thread_pool = _get_background_thread_pool


def submit_background_job(job_name: str, callback: Callable[[], None]) -> bool:
    """Submit optional work unless FastAPI shutdown has stopped media admission."""
    with _thread_pool_lock:
        if not _background_jobs_enabled:
            logger.info("Skipping background job during shutdown: %s", job_name)
            return False
        try:
            _get_background_thread_pool().submit(callback)
        except RuntimeError:
            logger.info("Skipping unavailable background job: %s", job_name)
            return False
    return True


def persist_rewritten_current_event(game_loop, game_id: int, rewritten_story: str) -> None:
    """Persist a rewritten current story so refresh/save/load use the new text."""
    if not rewritten_story or not getattr(game_loop, "current_event", None):
        return

    game_loop.current_event.event_description = rewritten_story

    player_state = getattr(game_loop, "player_state", None)
    if player_state is not None:
        current_event_data = getattr(player_state, "current_event_data", None)
        event_data = game_loop.current_event.model_dump()
        if not isinstance(event_data, dict):
            event_data = {}
        if isinstance(current_event_data, dict):
            event_data = {**current_event_data, **event_data}
        event_data["event_description"] = rewritten_story
        if isinstance(current_event_data, dict) and "story_text" in current_event_data:
            event_data["story_text"] = rewritten_story
        elif "story_text" in event_data:
            event_data["story_text"] = rewritten_story
        player_state.current_event_data = event_data

    try:
        db = get_db()
        state = player_state
        if state is None and hasattr(game_loop, "get_state"):
            state = game_loop.get_state()
        if state is not None:
            db.save_game_progress(game_id, state)
            logger.info(f"Auto-saved game state after rewrite: game_id={game_id}")
    except (OSError, IOError) as e:
        logger.warning(f"Auto-save IO error after rewrite: {e}")
    except Exception as e:
        logger.exception(f"Auto-save unexpected error after rewrite: {e}")


def shutdown_sse_thread_pool(
    wait: bool = True, prevent_new_background_jobs: bool = False
) -> None:
    """Close gameplay executors and optionally stop media admission permanently."""
    global _sse_thread_pool, _background_thread_pool, _background_jobs_enabled
    with _thread_pool_lock:
        if prevent_new_background_jobs:
            _background_jobs_enabled = False
        story_pool = _sse_thread_pool
        background_pool = _background_thread_pool
        _sse_thread_pool = None
        _background_thread_pool = None

    for pool in (story_pool, background_pool):
        if pool is not None:
            pool.shutdown(wait=wait, cancel_futures=not wait)


def build_round_illustration_job(
    game_loop, game_id: int, event, stage: str = "event"
) -> Optional[RoundIllustrationJob]:
    """Freeze event data before it can be delayed behind other media work."""
    player_state = getattr(game_loop, "player_state", None)
    story_text = getattr(event, "event_description", "") if event else ""
    if not player_state or not story_text:
        logger.warning("[RoundIllustration] Missing player state or story for game %s", game_id)
        return None

    return RoundIllustrationJob(
        game_id=game_id,
        week=int(player_state.week),
        round_number=int(player_state.current_round),
        stage=stage,
        story_text=str(story_text),
        character_settings=copy.deepcopy(player_state.character_settings or {}),
        player_name=str(player_state.player_name or "主角"),
        world_model_data=copy.deepcopy(player_state.world_model_data or {}),
        established_facts=copy.deepcopy(
            getattr(player_state, "established_facts", []) or []
        ),
    )


def _trigger_round_illustration_generation(
    game_loop, game_id: int, event, stage: str = "event"
) -> None:
    """Queue an event-scoped scene job without retaining mutable game state."""
    job = build_round_illustration_job(game_loop, game_id, event, stage)
    if job is None:
        return
    submit_background_job(
        f"round-illustration:{job.game_id}:{job.week}:{job.round_number}:{job.stage}",
        lambda: _generate_round_illustration(job),
    )


def _generate_round_illustration(job: RoundIllustrationJob) -> None:
    """Generate one scene entirely inside its bounded background worker."""
    try:
        from src.ai.image_client import ImageClient
        from src.database.models import Game
        from src.database.models import Image as ImageModel
        from src.database.models import SceneImage
        from src.database.models import SessionLocal
        from src.game.round.illustration_service import RoundIllustrationService
        from src.services.image_storage import ImageStorageService

        db = SessionLocal()
        try:
            game = db.query(Game).filter(Game.game_id == job.game_id).first()
            if not game:
                logger.warning("[RoundIllustration] Game %s not found", job.game_id)
                return

            existing = (
                db.query(SceneImage)
                .filter(
                    SceneImage.game_id == job.game_id,
                    SceneImage.week == job.week,
                    SceneImage.round_number == job.round_number,
                    SceneImage.stage == job.stage,
                )
                .first()
            )
            images = (
                db.query(ImageModel)
                .filter(ImageModel.game_id == job.game_id, ImageModel.is_active.is_(True))
                .all()
            )
            existing_images = [
                {
                    "image_id": image.image_id,
                    "entity_name": image.entity_name,
                    "image_type": image.image_type,
                    "entity_key": image.entity_key,
                }
                for image in images
            ]

            if existing:
                if settings.AUTO_GENERATE_ENTITY_IMAGES_FOR_SCENES:
                    snapshot_loop = SimpleNamespace(
                        player_state=SimpleNamespace(
                            character_settings=job.character_settings,
                            world_model_data=job.world_model_data,
                            established_facts=job.established_facts,
                        )
                    )
                    _ensure_entity_images_exist(
                        snapshot_loop,
                        job.game_id,
                        SimpleNamespace(event_description=job.story_text),
                        existing_images,
                        job.week,
                        job.round_number,
                    )
                return

            illustration_service = RoundIllustrationService(
                image_client=ImageClient(),
                image_storage=ImageStorageService(),
                db_session=db,
            )
            illustration_service.generate_round_illustration(
                game_id=job.game_id,
                round_number=job.round_number,
                story_text=job.story_text,
                character_settings=job.character_settings,
                player_name=job.player_name,
                existing_images=existing_images,
                stage=job.stage,
                week=job.week,
                world_model_data=job.world_model_data,
                established_facts=job.established_facts,
            )
        finally:
            db.close()
    except Exception as exc:
        logger.exception("[RoundIllustration] Unexpected error: %s", exc)


def _ensure_entity_images_exist(
    game_loop, game_id: int, event, existing_images: list, week: int, round_number: int
) -> None:
    """
    确保故事中涉及的所有实体（人物、物品、地点）都有图片。

    即使场景插画已存在，仍然需要检查并生成缺失的实体图片。
    这在断点续传场景特别重要：用户加载存档后，人物图片可能尚未生成。

    Args:
        game_loop: 游戏循环实例
        game_id: 游戏ID
        event: 事件对象
        existing_images: 已有的图片列表
        week: 周数
        round_number: 轮次
    """
    if not settings.AUTO_GENERATE_ENTITY_IMAGES_FOR_SCENES:
        logger.info("[RoundIllustration] Entity image backfill for scenes is disabled")
        return

    def ensure_images():
        try:
            from src.ai.image_client import ImageClient
            from src.database.models import SessionLocal
            from src.game.round.illustration_service import \
                RoundIllustrationService
            from src.services.image_storage import ImageStorageService

            db = SessionLocal()
            try:
                player_state = game_loop.player_state
                if not player_state:
                    return

                character_settings = player_state.character_settings or {}
                story_text = event.event_description if event else ""

                if not story_text:
                    return

                # 提取时代背景
                era = "现代"
                if character_settings.get("era"):
                    era_data = character_settings["era"]
                    if isinstance(era_data, dict):
                        era = era_data.get("era", "现代")
                    else:
                        era = str(era_data)

                # 创建服务实例
                image_client = ImageClient()
                image_storage = ImageStorageService()
                illustration_service = RoundIllustrationService(
                    image_client=image_client,
                    image_storage=image_storage,
                    db_session=db,
                )

                # 提取故事中涉及的实体
                world_model_data = player_state.world_model_data or {}
                established_facts = getattr(player_state, "established_facts", []) or []

                involved_entities = illustration_service._extract_involved_entities(
                    story_text,
                    character_settings,
                    world_model_data=world_model_data,
                    established_facts=established_facts,
                )

                # 检查每个实体是否有图片，没有则生成
                generated_count = 0
                for entity in involved_entities:
                    entity_name = entity.get("name")
                    entity_type = entity.get("type", "character")
                    entity_desc = entity.get("description", "")

                    # 检查是否已有图片
                    entity_image = illustration_service._find_entity_image(
                        existing_images, entity_name
                    )
                    if not entity_image:
                        # 没有图片，自动生成
                        logger.info(
                            f"[EntityImages] {entity_type} '{entity_name}' has no image, auto-generating..."
                        )
                        try:
                            new_image = illustration_service._generate_entity_image(
                                game_id=game_id,
                                entity_name=entity_name,
                                entity_type=entity_type,
                                description=entity_desc,
                                era=era,
                            )
                            if new_image:
                                generated_count += 1
                                logger.info(
                                    f"[EntityImages] Auto-generated {entity_type} image for '{entity_name}': image_id={new_image.image_id}"
                                )
                            else:
                                logger.warning(
                                    f"[EntityImages] _generate_entity_image returned None for '{entity_name}'"
                                )
                        except (OSError, IOError) as e:
                            logger.warning(
                                f"[EntityImages] IO error generating {entity_type} image for '{entity_name}': {e}"
                            )
                        except Exception as e:
                            logger.exception(
                                f"[EntityImages] Unexpected error generating {entity_type} image for '{entity_name}': {e}"
                            )

                if generated_count > 0:
                    week_display = f"第{week + 1}周" if week is not None else "未知周"
                    logger.info(
                        f"[EntityImages] Completed: generated {generated_count} images for {week_display} round {round_number}"
                    )

            finally:
                db.close()

        except Exception as e:
            logger.exception(f"[EntityImages] Unexpected error in ensure_images: {e}")

    submit_background_job(
        f"entity-backfill:{game_id}:{week}:{round_number}",
        ensure_images,
    )


def _prefetch_options(game_loop, game_id: int, session, event) -> None:
    """
    异步预生成选项并缓存。

    在故事生成完成后（但选项未生成时）后台触发，
    这样下次加载存档时可以直接使用缓存的选项，实现零等待。

    Args:
        game_loop: 游戏循环实例
        game_id: 游戏ID
        session: GameLoopSession 实例
        event: 事件对象（包含故事描述但没有选项）
    """

    def prefetch():
        try:
            if not session or session.is_prefetching_options():
                return

            player_state = game_loop.player_state
            if not player_state:
                return

            current_week = player_state.week
            current_round = player_state.current_round

            # Check if already cached
            story_description = event.event_description if event else ""
            cached = session.get_cached_options(current_week, current_round, story_description)
            if cached:
                logger.info(
                    f"[Options Prefetch] Already cached for week={current_week}, round={current_round}"
                )
                return

            session.start_prefetching_options()
            logger.info(
                f"[Options Prefetch] Starting for game_id={game_id}, "
                f"week={current_week}, round={current_round}"
            )

            # Generate options
            story_description = event.event_description
            ai_generator = game_loop.ai_generator

            options_event = ai_generator.generate_options_only(
                story_description=story_description,
                player_state=player_state.to_dict(),
                character_settings=player_state.character_settings,
                language=game_loop.language,
            )

            if options_event and options_event.options:
                # Cache the options
                session.set_cached_options(
                    current_week,
                    current_round,
                    [opt.model_dump() for opt in options_event.options],
                    story_description,
                )
                logger.info(
                    f"[Options Prefetch] Completed: cached {len(options_event.options)} options "
                    f"for game_id={game_id}"
                )
            else:
                logger.warning("[Options Prefetch] Failed: no options generated")

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"[Options Prefetch] Data error: {e}")
        except Exception as e:
            logger.exception(f"[Options Prefetch] Unexpected error: {e}")
        finally:
            if session:
                session.finish_prefetching_options()

    submit_background_job(f"options-prefetch:{game_id}", prefetch)


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


def _persist_generated_event_state(game_loop, game_id: int) -> None:
    """Persist generated event state immediately after worker generation returns."""
    try:
        db = get_db()
        state = game_loop.get_state()
        if state:
            db.save_game_progress(game_id, state)
            logger.info(f"Auto-saved game state after event generation: game_id={game_id}")
    except (OSError, IOError) as e:
        logger.warning(f"Auto-save IO error after event generation: {e}")
    except Exception as e:
        logger.exception(f"Auto-save unexpected error after event generation: {e}")


def _set_generation_resume_view(
    game_loop,
    game_id: int,
    phase: str,
    error: str = "",
) -> None:
    """Persist a recoverable visible phase around the durable worker."""
    player_state = getattr(game_loop, "player_state", None)
    if player_state is None:
        return
    if phase == "options":
        player_state.resume_view = None
    else:
        player_state.resume_view = {
            "phase": phase,
            "story_text": "",
            "round_summary": "",
            "summary_text": "",
            "error": error,
            "completed_week": int(player_state.week),
            "completed_round": int(player_state.current_round),
        }
    _persist_generated_event_state(game_loop, game_id)


def _persist_choice_state(game_loop, game_id: int) -> None:
    """Persist choice result state immediately after worker choice processing returns."""
    try:
        db = get_db()
        state = game_loop.get_state()
        if state:
            db.save_game_progress(game_id, state)
            logger.info(f"Auto-saved game state after choice: game_id={game_id}")
    except (OSError, IOError) as e:
        logger.warning(f"Auto-save IO error after choice: {e}")
    except Exception as e:
        logger.exception(f"Auto-save unexpected error after choice: {e}")


def build_event_generation_key(game_id: int, game_loop) -> EventGenerationKey:
    """Build the stable identity for the current round event."""
    player_state = game_loop.player_state
    return EventGenerationKey(
        game_id=game_id,
        week=int(player_state.week),
        round_number=int(player_state.current_round),
        stage="event",
    )


def _run_event_generation_operation(operation, game_loop, game_id: int, session) -> None:
    """Run one event generation job independently of all SSE subscribers."""
    try:
        event = game_loop.generate_round_event(
            stream_callback=operation.publish_story,
            status_callback=operation.publish_phase,
            session=session,
        )
        if event is None:
            raise RuntimeError("No event returned from event generation")
        _set_generation_resume_view(game_loop, game_id, "options")
        operation.complete(event)
        try:
            _trigger_round_illustration_generation(game_loop, game_id, event, stage="event")
        except Exception as exc:
            logger.exception("Failed to trigger round illustration: %s", exc)
    except Exception as exc:
        logger.exception("Event generation operation failed: %s", exc)
        _set_generation_resume_view(game_loop, game_id, "failed", str(exc))
        operation.fail(str(exc))


def get_or_start_round_event_generation(game_loop, game_id: int, session):
    """Return the current operation and start its worker exactly once."""
    key = build_event_generation_key(game_id, game_loop)
    operation, should_start = session.event_generation.get_or_create(key)
    if should_start:
        _set_generation_resume_view(game_loop, game_id, "generating")
        _get_sse_thread_pool().submit(
            _run_event_generation_operation,
            operation,
            game_loop,
            game_id,
            session,
        )
    return operation, should_start


async def wait_for_event_generation(operation, timeout: float = SSE_STREAM_TIMEOUT):
    """Wait for a terminal snapshot without cancelling the background job."""
    deadline = asyncio.get_running_loop().time() + timeout
    while operation.status == "running":
        if asyncio.get_running_loop().time() >= deadline:
            raise asyncio.TimeoutError
        await asyncio.sleep(0.1)
    return operation.snapshot_after(-1)


async def stream_round_event(
    game_loop, game_id: int, session=None, last_event_id: Optional[int] = None
):
    """Subscribe to one durable round-event generation operation."""
    if session is None:
        from src.api.session_store import GameLoopSession

        session = GameLoopSession(game_loop=game_loop, game_id=game_id)

    try:
        operation, should_start = get_or_start_round_event_generation(
            game_loop, game_id, session
        )
    except EventGenerationConflict as exc:
        yield make_sse_event("error", {"error": str(exc)})
        return

    cursor = -1 if last_event_id is None else last_event_id
    last_phase = ""
    last_heartbeat = asyncio.get_running_loop().time()
    yield make_sse_event(
        "status", {"phase": "preparing" if should_start else "resuming"}
    )

    while True:
        snapshot = operation.snapshot_after(cursor)
        if snapshot.phase != last_phase:
            last_phase = snapshot.phase
            yield make_sse_event("status", {"phase": snapshot.phase})
        for event_id, chunk in snapshot.chunks:
            cursor = event_id
            yield make_sse_event("story", chunk, event_id=event_id)

        if snapshot.status == "completed":
            yield make_sse_event("complete", snapshot.result.model_dump())
            return
        if snapshot.status == "failed":
            yield make_sse_event(
                "error", {"error": snapshot.error or "Event generation failed"}
            )
            return

        now = asyncio.get_running_loop().time()
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            last_heartbeat = now
            yield make_sse_event(
                "status", {"phase": snapshot.phase, "heartbeat": True}
            )
        await asyncio.sleep(0.1)


async def stream_choice(
    game_loop,
    option_index: int,
    game_id: int,
    session=None,
    last_event_id: Optional[int] = None,
    is_custom: bool = False,
    custom_text: str = "",
):
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
            if result_holder[0] is not None:
                _persist_choice_state(game_loop, game_id)
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"[stream_choice] Data error in run(): {e}")
            error_holder[0] = e
        except Exception as e:
            logger.exception(f"[stream_choice] Unexpected error in run(): {e}")
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
            logger.info(
                f"Replaying {len(cached_chunks)} cached chunks from event_id={last_event_id + 1}"
            )
            yield make_sse_event(
                "status", {"phase": "replaying", "cached_count": len(cached_chunks)}
            )
            for event_id, chunk in cached_chunks:
                yield make_sse_event("story", chunk, event_id=event_id)

    # Immediately tell the client we're alive and processing
    yield make_sse_event("status", {"phase": "preparing"})

    _get_sse_thread_pool().submit(run)

    # Heartbeat + timeout: use module-level constants
    last_event_time = asyncio.get_event_loop().time()

    while True:
        try:
            event_type, data = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_INTERVAL)
            last_event_time = asyncio.get_event_loop().time()
        except asyncio.TimeoutError:
            # Check if overall timeout exceeded
            elapsed = asyncio.get_event_loop().time() - last_event_time
            if elapsed > SSE_STREAM_TIMEOUT:
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

    if error_holder[0] is not None:
        yield make_sse_event("error", {"error": str(error_holder[0])})
        # Clear cache on error
        if session is not None:
            session.clear_sse_cache()
        return

    result = result_holder[0]
    if result is not None:
        yield make_sse_event("complete", result)
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
    logger.info(
        f"Reconnection after completion, sending complete event directly (last_event_id={last_event_id})"
    )
    yield make_sse_event("status", {"phase": "resuming"})
    yield make_sse_event("complete", event.model_dump())


async def stream_regenerate(
    game_loop, game_id: int, session=None, last_event_id: Optional[int] = None
):
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
            if hasattr(game_loop, "_event_generator_service"):
                game_loop._event_generator_service._generating = False
                game_loop._event_generator_service._generating_start_time = None

            # 清空当前事件，让 generate_round_event 生成全新事件
            game_loop.current_event = None

            # ★ CRITICAL: 显式清除 event generator 内部缓存
            # property setter 应该已经处理了，但多线程场景下增加防御性清除
            if hasattr(game_loop, "_event_generator_service"):
                game_loop._event_generator_service._current_event = None
                logger.info(
                    "[stream_regenerate] Explicitly cleared _event_generator_service._current_event"
                )

            # ★ CRITICAL: 清除 player_state 中的故事缓存，确保真正重新生成
            # 否则 generate_round_event 会从 last_round_full_story 恢复旧故事
            player_state = game_loop.player_state
            current_week = None
            current_round = None
            if player_state:
                current_week = player_state.week
                current_round = player_state.current_round

                # 清除 last_round_full_story 强制重新生成故事
                if hasattr(player_state, "last_round_full_story"):
                    player_state.last_round_full_story = (
                        ""  # 使用空字符串而不是 None，避免 Pydantic 验证错误
                    )
                # 清除当前轮次的 round_history 条目
                if hasattr(player_state, "round_history") and player_state.round_history:
                    # 过滤掉当前轮次的历史记录
                    original_count = len(player_state.round_history)
                    player_state.round_history = [
                        entry
                        for entry in player_state.round_history
                        if not (
                            entry.get("week") == current_week
                            and entry.get("round") == current_round
                        )
                    ]
                    removed_count = original_count - len(player_state.round_history)
                    logger.info(
                        f"[stream_regenerate] Removed {removed_count} round_history entries for week={current_week}, round={current_round}"
                    )
                # ★ CRITICAL: 清除 current_event_data，防止从保存的状态恢复
                if hasattr(player_state, "current_event_data"):
                    player_state.current_event_data = None
                    logger.info("[stream_regenerate] Cleared current_event_data")
                logger.info("[stream_regenerate] Cleared story caches for true regeneration")

                # ★ CRITICAL: 清除 session 缓存的选项，防止使用旧选项
                if session is not None:
                    session.clear_options_cache()
                    session.clear_sse_cache()
                    logger.info("[stream_regenerate] Cleared session options and SSE cache")

            # ★ CRITICAL: 删除当前轮次的场景图片记录，确保重新生成图片
            # 否则系统会认为图片已存在，不会生成新的图片
            if current_week is not None and current_round is not None:
                try:
                    from src.database.models import SceneImage, SessionLocal

                    db = SessionLocal()
                    try:
                        # 删除当前周、当前轮次的所有场景图片记录
                        deleted = (
                            db.query(SceneImage)
                            .filter(
                                SceneImage.game_id == game_id,
                                SceneImage.week == current_week,
                                SceneImage.round_number == current_round,
                            )
                            .delete()
                        )
                        db.commit()
                        if deleted > 0:
                            logger.info(
                                f"[stream_regenerate] Deleted {deleted} old scene image(s) for "
                                f"week={current_week}, round={current_round}"
                            )
                    finally:
                        db.close()
                except Exception as e:
                    logger.warning(f"[stream_regenerate] Failed to delete old scene images: {e}")

            # 调用 game_loop 的完整生成流程
            new_event = game_loop.generate_round_event(
                stream_callback=stream_cb,
                status_callback=status_cb,
                session=session,  # ★ 传递 session 以支持选项缓存
            )

            if new_event and new_event.options:
                result_holder[0] = new_event
                logger.info(
                    f"Regeneration complete: {len(new_event.event_description)} chars, {len(new_event.options)} options"
                )
            else:
                error_holder[0] = ValueError("Failed to generate valid event with options")

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"[stream_regenerate] Data error: {e}")
            error_holder[0] = e
        except Exception as e:
            logger.exception(f"[stream_regenerate] Unexpected error: {e}")
            error_holder[0] = e
        finally:
            logger.info(
                f"[stream_regenerate] run() finally block, closed={closed[0]}, loop_closed={loop.is_closed()}"
            )
            if not closed[0] and not loop.is_closed():
                try:
                    loop.call_soon_threadsafe(q.put_nowait, ("__done__", None))
                    logger.info("[stream_regenerate] Sent __done__ signal")
                except RuntimeError as e:
                    logger.warning(f"[stream_regenerate] Failed to send __done__: {e}")
            else:
                logger.warning(
                    f"[stream_regenerate] Skipped sending __done__, closed={closed[0]}, loop_closed={loop.is_closed()}"
                )

    # Tell client we're starting
    yield make_sse_event("status", {"phase": "regenerating"})

    _get_sse_thread_pool().submit(run)

    # Heartbeat + timeout: use module-level constants
    last_event_time = asyncio.get_event_loop().time()

    while True:
        try:
            event_type, data = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_INTERVAL)
            last_event_time = asyncio.get_event_loop().time()
        except asyncio.TimeoutError:
            elapsed = asyncio.get_event_loop().time() - last_event_time
            if elapsed > SSE_STREAM_TIMEOUT:
                yield make_sse_event("error", {"error": "Timeout during regeneration"})
                break
            yield make_sse_event("status", {"phase": "processing", "heartbeat": True})
            continue

        if event_type == "__done__":
            logger.info("[stream_regenerate] Received __done__ signal, breaking loop")
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

    if error_holder[0] is not None:
        yield make_sse_event("error", {"error": str(error_holder[0])})
        if session is not None:
            session.clear_sse_cache()
        return

    # Send complete event with full event data
    event = result_holder[0]
    logger.info(f"[stream_regenerate] Sending complete event, event is None: {event is None}")
    if event is not None:
        event_data = event.model_dump()
        logger.info(f"[stream_regenerate] Complete event data keys: {list(event_data.keys())}")
        yield make_sse_event("complete", event_data)

        # Auto-save game state
        try:
            db = get_db()
            state = game_loop.get_state()
            if state:
                db.save_game_progress(game_id, state)
                logger.info(f"Auto-saved game state after regeneration: game_id={game_id}")
        except (OSError, IOError) as e:
            logger.warning(f"Auto-save IO error after regeneration: {e}")
        except Exception as e:
            logger.exception(f"Auto-save unexpected error after regeneration: {e}")
    else:
        logger.info("[stream_regenerate] Sending empty complete event (event is None)")
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
                    player_state_dict = (
                        game_loop.player_state.to_dict()
                        if hasattr(game_loop.player_state, "to_dict")
                        else dict(game_loop.player_state.__dict__)
                    )
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"[Rewrite] Data error building WorldModel: {e}")
                except Exception as e:
                    logger.exception(f"[Rewrite] Unexpected error building WorldModel: {e}")

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

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"[stream_rewrite] Data error: {e}")
            error_holder[0] = e
        except Exception as e:
            logger.exception(f"[stream_rewrite] Unexpected error: {e}")
            error_holder[0] = e
        finally:
            if not closed[0] and not loop.is_closed():
                try:
                    loop.call_soon_threadsafe(q.put_nowait, ("__done__", None))
                except RuntimeError:
                    pass

    # Tell client we're starting
    yield make_sse_event("status", {"phase": "rewriting"})

    _get_sse_thread_pool().submit(run)

    # Heartbeat + timeout: use module-level constants
    last_event_time = asyncio.get_event_loop().time()

    while True:
        try:
            event_type, data = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_INTERVAL)
            last_event_time = asyncio.get_event_loop().time()
        except asyncio.TimeoutError:
            elapsed = asyncio.get_event_loop().time() - last_event_time
            if elapsed > SSE_STREAM_TIMEOUT:
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

    if error_holder[0] is not None:
        yield make_sse_event("error", {"error": str(error_holder[0])})
        if session is not None:
            session.clear_sse_cache()
        return

    # Send complete event with rewritten story
    rewritten_story = result_holder[0]
    if rewritten_story is not None:
        persist_rewritten_current_event(game_loop, game_id, rewritten_story)

        yield make_sse_event(
            "complete",
            {
                "new_story": rewritten_story,
                "rewritten_story": rewritten_story,
                "event": (
                    game_loop.current_event.model_dump() if game_loop.current_event else None
                ),
            },
        )

        # Clear SSE cache after successful completion
        if session is not None:
            session.clear_sse_cache()
    else:
        yield make_sse_event("complete", {"new_story": "", "rewritten_story": "", "event": None})
