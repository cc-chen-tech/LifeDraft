"""Speculative next-day generation for one recommended daily branch."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.ai.models import GameEvent
from src.game.round.daily_choice_processor import project_daily_choice
from src.services.daily_recommended_prefetch_repository import (
    DailyRecommendedPrefetchRepository,
)

logger = logging.getLogger(__name__)
_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


@dataclass(frozen=True)
class ChoicePrefetchResolution:
    task_id: Optional[int]
    fingerprint: str
    recommended_selected: bool
    next_event: Optional[GameEvent]


@dataclass(frozen=True)
class DemandedPrefetchProbe:
    task_id: Optional[int]
    status: str
    pending: bool
    event: Optional[GameEvent]


def canonical_prefetch_fingerprint(state: Any, event: GameEvent) -> str:
    """Hash canonical prompt state and current event identity deterministically."""

    if hasattr(state, "model_dump"):
        state_data = state.model_dump(mode="json")
    elif isinstance(state, dict):
        state_data = dict(state)
    else:
        raise TypeError("unsupported_player_state")
    state_data.pop("resume_view", None)
    payload = {
        "state": state_data,
        "event": event.model_dump(mode="json"),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def generate_speculative_next_event(
    state: Any,
    event: GameEvent,
    *,
    option_index: int,
    language: str,
    generate_event: Callable[[Any], GameEvent],
) -> GameEvent:
    """Generate from the canonical projected settlement without live mutation."""

    projection = project_daily_choice(
        state,
        event,
        option_index=option_index,
        language=language,
    )
    next_event = generate_event(projection.state)
    if not isinstance(next_event, GameEvent):
        raise RuntimeError("recommended_prefetch_returned_no_event")
    return next_event


def resolve_choice_prefetch(
    repository: DailyRecommendedPrefetchRepository,
    *,
    game_id: int,
    state: Any,
    event: GameEvent,
    option_index: int,
) -> ChoicePrefetchResolution:
    """Resolve a ready hit or mark the matching in-flight task as demanded."""

    fingerprint = canonical_prefetch_fingerprint(state, event)
    recommended = [
        index for index, option in enumerate(event.options) if option.likely_choice
    ]
    recommended_selected = recommended == [option_index]
    if not recommended_selected:
        repository.invalidate_event(
            game_id=game_id,
            event_id=event.event_id,
            revision=event.revision,
            selected_option_index=option_index,
        )
        logger.info(
            "daily_recommended_prefetch_metric action=choice selected=false "
            "game_id=%s event_id=%s option_index=%s",
            game_id,
            event.event_id,
            option_index,
        )
        return ChoicePrefetchResolution(
            task_id=None,
            fingerprint=fingerprint,
            recommended_selected=False,
            next_event=None,
        )

    task = repository.mark_demanded(
        game_id=game_id,
        event_id=event.event_id,
        revision=event.revision,
        option_index=option_index,
        state_fingerprint=fingerprint,
    )
    next_event = None
    if task is not None and task.status in {"story_ready", "ready"}:
        payload = task.next_event_json
        if isinstance(payload, dict):
            next_event = GameEvent.model_validate(payload)
    logger.info(
        "daily_recommended_prefetch_metric action=choice selected=true "
        "hit=%s status=%s game_id=%s event_id=%s option_index=%s",
        next_event is not None,
        getattr(task, "status", "absent"),
        game_id,
        event.event_id,
        option_index,
    )
    return ChoicePrefetchResolution(
        task_id=int(task.prefetch_id) if task is not None else None,
        fingerprint=fingerprint,
        recommended_selected=True,
        next_event=next_event,
    )


def resolve_choice_prefetch_for_game(
    *, game_id: int, game_loop: Any, option_index: int
) -> ChoicePrefetchResolution:
    """Resolve and durably record one live choice against its speculative job."""

    from src.database.models import SessionLocal

    event = game_loop.current_event
    state = game_loop.player_state
    if event is None or state is None:
        return ChoicePrefetchResolution(None, "", False, None)
    db = SessionLocal()
    try:
        resolution = resolve_choice_prefetch(
            DailyRecommendedPrefetchRepository(db),
            game_id=game_id,
            state=state,
            event=event,
            option_index=option_index,
        )
        db.commit()
        return resolution
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def finalize_choice_prefetch(resolution: ChoicePrefetchResolution) -> None:
    """Consume a ready hit only after canonical choice persistence succeeds."""

    if resolution.task_id is None or resolution.next_event is None:
        return
    from src.database.models import SessionLocal

    db = SessionLocal()
    try:
        DailyRecommendedPrefetchRepository(db).consume_task(resolution.task_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def invalidate_daily_recommended_prefetch_for_current_event(
    *, game_id: int, game_loop: Any
) -> int:
    """Fence speculative output before a rewrite, regeneration, or custom choice."""

    from config.feature_flags import get_feature
    from src.database.models import SessionLocal

    if not get_feature("daily_recommended_prefetch"):
        return 0
    event = getattr(game_loop, "current_event", None)
    if event is None:
        return 0
    db = SessionLocal()
    try:
        count = DailyRecommendedPrefetchRepository(db).invalidate_event(
            game_id=game_id,
            event_id=str(event.event_id),
            revision=int(event.revision),
        )
        db.commit()
        return count
    except Exception:
        db.rollback()
        logger.exception("Failed to invalidate daily recommended prefetch")
        return 0
    finally:
        db.close()


def _get_prefetch_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="daily-recommended-prefetch"
            )
        return _executor


def shutdown_daily_recommended_prefetch(wait: bool = True) -> None:
    global _executor
    with _executor_lock:
        executor = _executor
        _executor = None
    if executor is not None:
        executor.shutdown(wait=wait, cancel_futures=not wait)


def cleanup_expired_daily_recommended_prefetch(
    *, now: Optional[datetime] = None, retention_days: int = 7
) -> int:
    """Remove expired speculative rows and unconsumed narration assets."""

    from sqlalchemy import or_

    from src.database.models import (
        DailyRecommendedPrefetch,
        GeneratedVoiceAsset,
        SessionLocal,
        VoiceReadingJob,
        VoiceReadingSegment,
    )
    from src.services.story_tts_provider import generated_voice_file_path

    cutoff = (now or datetime.utcnow()) - timedelta(days=retention_days)
    db = SessionLocal()
    files_to_remove: set[Path] = set()
    removed = 0
    try:
        expired = (
            db.query(DailyRecommendedPrefetch)
            .filter(
                DailyRecommendedPrefetch.updated_at < cutoff,
                or_(
                    DailyRecommendedPrefetch.status.in_(
                        {"failed", "invalidated", "consumed"}
                    ),
                    (
                        DailyRecommendedPrefetch.status.in_(
                            {"queued", "processing", "story_ready", "ready"}
                        )
                        & DailyRecommendedPrefetch.demanded.is_(False)
                    ),
                ),
            )
            .all()
        )
        for task in expired:
            # Consumed narration is now formal story media and must survive the
            # speculative task's retention window.
            raw_job_id = getattr(task, "tts_job_id", None)
            job = db.get(VoiceReadingJob, int(raw_job_id)) if raw_job_id else None
            if job is not None and task.status != "consumed":
                other_task_count = (
                    db.query(DailyRecommendedPrefetch)
                    .filter(
                        DailyRecommendedPrefetch.tts_job_id == job.job_id,
                        DailyRecommendedPrefetch.prefetch_id != task.prefetch_id,
                    )
                    .count()
                )
                if other_task_count == 0:
                    asset_ids = {
                        int(asset_id)
                        for asset_id in [job.asset_id]
                        + [segment.asset_id for segment in job.segments]
                        if asset_id is not None
                    }
                    setattr(task, "tts_job_id", None)
                    db.flush()
                    db.delete(job)
                    db.flush()
                    for asset_id in asset_ids:
                        referenced = (
                            db.query(VoiceReadingJob)
                            .filter(VoiceReadingJob.asset_id == asset_id)
                            .count()
                            + db.query(VoiceReadingSegment)
                            .filter(VoiceReadingSegment.asset_id == asset_id)
                            .count()
                        )
                        asset = db.get(GeneratedVoiceAsset, asset_id)
                        if (
                            referenced == 0
                            and asset is not None
                            and asset.source_type == "recommended_prefetch"
                        ):
                            file_name = Path(
                                urlparse(str(asset.storage_path)).path
                            ).name
                            file_path = generated_voice_file_path(file_name)
                            if file_path is not None:
                                files_to_remove.add(file_path)
                            db.delete(asset)
            db.delete(task)
            removed += 1
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to clean expired daily recommended prefetches")
        return 0
    finally:
        db.close()

    for file_path in files_to_remove:
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove expired narration asset %s", file_path)
    if removed:
        logger.info(
            "daily_recommended_prefetch_metric action=cleanup removed=%s",
            removed,
        )
    return removed


def ensure_daily_recommended_prefetch(
    *,
    game_id: int,
    user_id: Optional[int],
    game_loop: Any,
    submitter: Optional[Callable[[Callable[[], None]], Any]] = None,
) -> Optional[int]:
    """Idempotently enqueue the current daily event's recommended branch."""

    from config.feature_flags import get_feature
    from src.database.models import SessionLocal
    from src.game.daily_timeline import is_daily_timeline, normalize_daily_timeline

    if not get_feature("daily_recommended_prefetch"):
        return None
    cleanup_expired_daily_recommended_prefetch()
    state = getattr(game_loop, "player_state", None)
    event = getattr(game_loop, "current_event", None)
    if state is None or event is None or not is_daily_timeline(state):
        return None
    recommended = [
        index for index, option in enumerate(event.options) if option.likely_choice
    ]
    if len(recommended) != 1:
        logger.warning(
            "Skipping daily recommended prefetch without exactly one "
            "recommendation: game=%s event=%s",
            game_id,
            event.event_id,
        )
        return None
    timeline = normalize_daily_timeline(state.timeline)
    fingerprint = canonical_prefetch_fingerprint(state, event)
    snapshot_state = state.model_copy(deep=True)
    snapshot_event = event.model_copy(deep=True)

    db = SessionLocal()
    try:
        voice_id = None
        voice_speed = None
        if user_id is not None and get_feature("daily_recommended_tts_prefetch"):
            from src.services.story_voice_reading import (
                story_auto_read_default_enabled,
            )
            from src.services.story_voice_repository import (
                StoryVoiceReadingRepository,
            )

            settings = StoryVoiceReadingRepository(db).get_settings(user_id)
            auto_read_enabled = (
                bool(settings.auto_read_enabled)
                if settings is not None
                else story_auto_read_default_enabled()
            )
            if auto_read_enabled:
                voice_id = (
                    str(settings.selected_voice_color)
                    if settings is not None and settings.selected_voice_color
                    else "warm_female"
                )
                voice_speed = (
                    float(settings.selected_speed)
                    if settings is not None and settings.selected_speed is not None
                    else 1.0
                )
        task = DailyRecommendedPrefetchRepository(db).enqueue(
            game_id=game_id,
            user_id=user_id,
            event_id=event.event_id,
            revision=event.revision,
            day_index=int(timeline["day_index"]),
            option_index=recommended[0],
            state_fingerprint=fingerprint,
            voice_id=voice_id,
            voice_speed=voice_speed,
        )
        task_id = int(task.prefetch_id)
        saved_voice_id = str(task.voice_id) if task.voice_id is not None else None
        saved_voice_speed = (
            float(task.voice_speed) if task.voice_speed is not None else None
        )
        saved_status = str(task.status)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to enqueue daily recommended prefetch")
        return None
    finally:
        db.close()

    logger.info(
        "daily_recommended_prefetch_metric action=shown task_id=%s "
        "game_id=%s event_id=%s option_index=%s status=%s tts_requested=%s",
        task_id,
        game_id,
        event.event_id,
        recommended[0],
        saved_status,
        saved_voice_id is not None,
    )

    def callback() -> None:
        _run_prefetch_worker(
            task_id=task_id,
            source_loop=game_loop,
            snapshot_state=snapshot_state,
            snapshot_event=snapshot_event,
            option_index=recommended[0],
            language=str(getattr(game_loop, "language", "zh") or "zh"),
            user_id=user_id,
            game_id=game_id,
            voice_id=saved_voice_id,
            voice_speed=saved_voice_speed,
        )
    if submitter is not None:
        submitter(callback)
    else:
        _get_prefetch_executor().submit(callback)
    return task_id


def _generate_with_isolated_game_loop(source_loop: Any, projected_state: Any) -> GameEvent:
    from src.game.game_loop import GameLoop

    speculative_loop = GameLoop(
        language=str(getattr(source_loop, "language", "zh") or "zh"),
        ai_generator=source_loop.ai_generator,
        quality_level=getattr(source_loop, "quality_level", None),
    )
    speculative_loop.player_state = projected_state
    speculative_loop.current_event = None
    event = speculative_loop.generate_round_event(
        session=None,
        operation_id="daily-recommended-prefetch",
    )
    if event is None:
        raise RuntimeError("recommended_prefetch_returned_no_event")
    return event


def _run_prefetch_worker(
    *,
    task_id: int,
    source_loop: Any,
    snapshot_state: Any,
    snapshot_event: GameEvent,
    option_index: int,
    language: str,
    user_id: Optional[int],
    game_id: int,
    voice_id: Optional[str] = None,
    voice_speed: Optional[float] = None,
) -> None:
    from src.database.models import SessionLocal

    claim_db = SessionLocal()
    try:
        token = DailyRecommendedPrefetchRepository(claim_db).claim(task_id)
        claim_db.commit()
    except Exception:
        claim_db.rollback()
        logger.exception("Failed to claim daily recommended prefetch %s", task_id)
        return
    finally:
        claim_db.close()
    if token is None:
        return

    generation_started = time.monotonic()
    try:
        projection = project_daily_choice(
            snapshot_state,
            snapshot_event,
            option_index=option_index,
            language=language,
        )
        next_event = _generate_with_isolated_game_loop(source_loop, projection.state)
        ready_db = SessionLocal()
        try:
            stored = DailyRecommendedPrefetchRepository(ready_db).mark_story_ready(
                task_id, token, next_event.model_dump(mode="json")
            )
            ready_db.commit()
        except Exception:
            ready_db.rollback()
            raise
        finally:
            ready_db.close()
        if not stored:
            return
        logger.info(
            "daily_recommended_prefetch_metric action=story_ready task_id=%s "
            "game_id=%s duration_ms=%s model_calls=1",
            task_id,
            game_id,
            int((time.monotonic() - generation_started) * 1000),
        )

        _promote_demanded_prefetch(
            task_id=task_id,
            game_id=game_id,
            game_loop=source_loop,
        )
        if user_id is not None and voice_id is not None and voice_speed is not None:
            _prefetch_story_voice(
                task_id=task_id,
                user_id=user_id,
                game_id=game_id,
                projected_state=projection.state,
                event=next_event,
                voice_id=voice_id,
                speed=voice_speed,
            )
    except Exception as error:
        failed_db = SessionLocal()
        try:
            DailyRecommendedPrefetchRepository(failed_db).mark_failed(
                task_id, token, error
            )
            failed_db.commit()
        except Exception:
            failed_db.rollback()
            logger.exception("Failed to persist recommended prefetch failure")
        finally:
            failed_db.close()
        logger.exception("Daily recommended prefetch failed: task=%s", task_id)


def _run_demanded_prefetch_worker(
    *,
    task_id: int,
    source_loop: Any,
    projected_state: Any,
    game_id: int,
) -> None:
    """Recover a queued or expired demanded job from committed next-day state."""

    from src.database.models import DailyRecommendedPrefetch, SessionLocal

    claim_db = SessionLocal()
    try:
        repository = DailyRecommendedPrefetchRepository(claim_db)
        token = repository.claim(task_id)
        task = claim_db.get(DailyRecommendedPrefetch, task_id)
        user_id = int(task.user_id) if task is not None and task.user_id is not None else None
        voice_id = str(task.voice_id) if task is not None and task.voice_id else None
        voice_speed = (
            float(task.voice_speed)
            if task is not None and task.voice_speed is not None
            else None
        )
        claim_db.commit()
    except Exception:
        claim_db.rollback()
        logger.exception("Failed to recover demanded recommended prefetch %s", task_id)
        return
    finally:
        claim_db.close()
    if token is None:
        return

    generation_started = time.monotonic()
    try:
        next_event = _generate_with_isolated_game_loop(source_loop, projected_state)
        ready_db = SessionLocal()
        try:
            stored = DailyRecommendedPrefetchRepository(ready_db).mark_story_ready(
                task_id, token, next_event.model_dump(mode="json")
            )
            ready_db.commit()
        except Exception:
            ready_db.rollback()
            raise
        finally:
            ready_db.close()
        if not stored:
            return
        logger.info(
            "daily_recommended_prefetch_metric action=story_ready task_id=%s "
            "game_id=%s duration_ms=%s model_calls=1 recovered=true",
            task_id,
            game_id,
            int((time.monotonic() - generation_started) * 1000),
        )
        _promote_demanded_prefetch(
            task_id=task_id,
            game_id=game_id,
            game_loop=source_loop,
        )
        if user_id is not None and voice_id is not None and voice_speed is not None:
            _prefetch_story_voice(
                task_id=task_id,
                user_id=user_id,
                game_id=game_id,
                projected_state=projected_state,
                event=next_event,
                voice_id=voice_id,
                speed=voice_speed,
            )
    except Exception as error:
        failed_db = SessionLocal()
        try:
            DailyRecommendedPrefetchRepository(failed_db).mark_failed(
                task_id, token, error
            )
            failed_db.commit()
        except Exception:
            failed_db.rollback()
            logger.exception("Failed to persist recovered prefetch failure")
        finally:
            failed_db.close()
        logger.exception("Demanded recommended prefetch recovery failed: task=%s", task_id)


def probe_demanded_prefetch(
    *,
    game_id: int,
    game_loop: Any,
    submitter: Optional[Callable[[Callable[[], None]], Any]] = None,
) -> DemandedPrefetchProbe:
    """Join the speculative job selected by the latest committed daily choice."""

    from src.database.models import SessionLocal

    state = getattr(game_loop, "player_state", None)
    history = getattr(state, "day_history", None) or []
    latest = history[-1] if history else None
    if not isinstance(latest, dict) or not latest.get("recommendation_selected"):
        return DemandedPrefetchProbe(None, "absent", False, None)
    event_id = str(latest.get("event_id") or "")
    revision = int(latest.get("revision") or 0)
    option_index = latest.get("choice_option_index")
    day_index = latest.get("day_index")
    if not event_id or not isinstance(option_index, int) or not isinstance(day_index, int):
        return DemandedPrefetchProbe(None, "absent", False, None)

    db = SessionLocal()
    try:
        task = DailyRecommendedPrefetchRepository(db).find_demanded_after_choice(
            game_id=game_id,
            event_id=event_id,
            revision=revision,
            option_index=option_index,
            day_index=day_index,
        )
        if task is None or task.status in {"failed", "invalidated"}:
            return DemandedPrefetchProbe(
                int(task.prefetch_id) if task is not None else None,
                str(task.status) if task is not None else "absent",
                False,
                None,
            )
        task_id = int(task.prefetch_id)
        status = str(task.status)
        payload = task.next_event_json if isinstance(task.next_event_json, dict) else None
        should_recover = status == "queued" or (
            status == "processing"
            and (
                task.lease_expires_at is None
                or task.lease_expires_at <= datetime.utcnow()
            )
        )
    finally:
        db.close()

    if payload is not None and status in {"story_ready", "ready", "consumed"}:
        event = GameEvent.model_validate(payload)
        _promote_demanded_prefetch(
            task_id=task_id,
            game_id=game_id,
            game_loop=game_loop,
        )
        return DemandedPrefetchProbe(task_id, status, False, event)
    if status in {"story_ready", "ready", "consumed"}:
        logger.warning(
            "Ignoring recommended prefetch terminal row without event payload: "
            "task=%s status=%s",
            task_id,
            status,
        )
        return DemandedPrefetchProbe(task_id, status, False, None)

    if should_recover and state is not None:
        projected_state = state.model_copy(deep=True)

        def callback() -> None:
            _run_demanded_prefetch_worker(
                task_id=task_id,
                source_loop=game_loop,
                projected_state=projected_state,
                game_id=game_id,
            )
        if submitter is not None:
            submitter(callback)
        else:
            _get_prefetch_executor().submit(callback)
    return DemandedPrefetchProbe(task_id, status, True, None)


def _prefetch_story_voice(
    *,
    task_id: int,
    user_id: int,
    game_id: int,
    projected_state: Any,
    event: GameEvent,
    voice_id: str,
    speed: float,
) -> None:
    from config.feature_flags import get_feature
    from src.api.schemas import ReadingContext, StoryVoiceReadingRequest
    from src.database.models import SessionLocal
    from src.services.story_voice_reading import (
        StoryVoiceReadingService,
        normalize_text_hash,
    )
    from src.services.story_voice_repository import StoryVoiceReadingRepository

    if not get_feature("daily_recommended_tts_prefetch"):
        return
    db = SessionLocal()
    tts_started = time.monotonic()
    try:
        service = StoryVoiceReadingService(StoryVoiceReadingRepository(db))
        timeline = projected_state.timeline or {}
        request = StoryVoiceReadingRequest(
            context=ReadingContext(
                source_type="recommended_prefetch",
                game_id=game_id,
                week=int(projected_state.week),
                round_number=int(projected_state.current_round),
                stage="event",
                attempt_id=f"recommended-prefetch-{task_id}",
                day_index=int(timeline.get("day_index") or 0),
                story_date=event.story_date,
                text_hash=normalize_text_hash(event.event_description),
                text=event.event_description,
            ),
            voice_id=voice_id,
            speed=speed,
            auto_play=False,
        )
        response: Any = service.request_recommended_prefetch(user_id, request)
        db.commit()
        if response.status == "queued":
            response = service.process_job(user_id, response.job_id)
            db.commit()
        DailyRecommendedPrefetchRepository(db).attach_tts(
            task_id,
            job_id=response.job_id,
            voice_id=voice_id,
            speed=speed,
            ready=response.status == "ready",
        )
        db.commit()
        logger.info(
            "daily_recommended_prefetch_metric action=tts_terminal task_id=%s "
            "game_id=%s status=%s duration_ms=%s voice_id=%s speed=%s",
            task_id,
            game_id,
            response.status,
            int((time.monotonic() - tts_started) * 1000),
            voice_id,
            speed,
        )
    except Exception:
        db.rollback()
        logger.exception("Recommended narration prefetch failed: task=%s", task_id)
    finally:
        db.close()


def _promote_demanded_prefetch(*, task_id: int, game_id: int, game_loop: Any) -> bool:
    """Promote an in-flight hit after its canonical choice has already committed."""

    from src.database.models import DailyRecommendedPrefetch, SessionLocal
    from src.database.singletons import get_game_db

    db = SessionLocal()
    try:
        task = db.get(DailyRecommendedPrefetch, task_id)
        if (
            task is None
            or not task.demanded
            or task.status not in {"story_ready", "ready", "consumed"}
            or not isinstance(task.next_event_json, dict)
        ):
            return False
        next_event = GameEvent.model_validate(task.next_event_json)
        lock = getattr(game_loop, "_daily_mutation_lock", threading.RLock())
        with lock:
            state = getattr(game_loop, "player_state", None)
            if state is None or game_loop.current_event is not None:
                return False
            history = state.day_history or []
            latest = history[-1] if history else {}
            timeline = state.timeline or {}
            if (
                latest.get("event_id") != task.event_id
                or latest.get("choice_option_index") != task.option_index
                or int(timeline.get("day_index") or -1) != task.day_index + 1
            ):
                return False
            state.current_event_data = next_event.model_dump()
            game_loop.current_event = next_event
            if not get_game_db().save_game_progress(game_id, state):
                state.current_event_data = None
                game_loop.current_event = None
                return False
            if task.status != "consumed":
                DailyRecommendedPrefetchRepository(db).consume_task(task_id)
            db.commit()
            return True
    except Exception:
        db.rollback()
        logger.exception("Failed to promote demanded recommended prefetch")
        return False
    finally:
        db.close()
