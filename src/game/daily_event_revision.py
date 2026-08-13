"""Candidate-first replacement of the one mutable event for the current day."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from src.ai.models import GameEvent


def _require_current(loop: Any) -> GameEvent:
    current = getattr(loop, "current_event", None)
    if current is None:
        raise ValueError("No current daily event")
    return current


def _mutation_lock(loop: Any) -> Any:
    lock = getattr(loop, "_daily_mutation_lock", None)
    if lock is None:
        lock = RLock()
        setattr(loop, "_daily_mutation_lock", lock)
    return lock


def _restore_state(loop: Any, original_state: Any, original: GameEvent) -> None:
    for field_name in type(loop.player_state).model_fields:
        setattr(
            loop.player_state,
            field_name,
            deepcopy(getattr(original_state, field_name)),
        )
    loop.current_event = original.model_copy(deep=True)


def _commit_candidate(
    loop: Any,
    original: GameEvent,
    candidate: GameEvent,
    persist_callback: Any = None,
) -> GameEvent:
    if not candidate.event_description or len(candidate.options) < 2:
        raise ValueError("invalid_daily_event_candidate")
    current = _require_current(loop)
    if current.event_id != original.event_id or current.revision != original.revision:
        raise ValueError("stale_daily_event_replacement")
    timeline = loop.player_state.timeline
    if original.story_date and timeline.get("current_date") != original.story_date:
        raise ValueError("stale_daily_event_replacement")
    committed = candidate.model_copy(deep=True)
    committed.event_id = original.event_id
    committed.revision = original.revision + 1
    committed.story_date = original.story_date
    loop.current_event = committed
    loop.player_state.current_event_data = committed.model_dump()
    if persist_callback is not None and not persist_callback(loop.player_state):
        raise RuntimeError("daily_event_persistence_failed")
    return committed


def regenerate_daily_event_atomically(
    loop: Any, *, persist_callback: Any = None, **generation_kwargs: Any
) -> GameEvent:
    """Generate a full candidate while keeping the current event recoverable."""
    with _mutation_lock(loop):
        original = _require_current(loop).model_copy(deep=True)
        original_state = loop.player_state.model_copy(deep=True)
        try:
            # Existing generators cache the current event, so isolate that mutation
            # and restore on every failure.
            loop.current_event = None
            loop.player_state.current_event_data = None
            candidate = loop.generate_round_event(**generation_kwargs)
            if candidate is None:
                raise ValueError("invalid_daily_event_candidate")
            # Full generation has legacy side effects (character introduction,
            # scheduled-event flags, relationship markers). Candidate creation
            # must not publish any of them; only the validated event is mutable.
            _restore_state(loop, original_state, original)
            return _commit_candidate(
                loop, original, candidate, persist_callback=persist_callback
            )
        except Exception:
            _restore_state(loop, original_state, original)
            raise


def rewrite_daily_event_atomically(
    loop: Any,
    *,
    full_story: str,
    segment_to_replace: str,
    user_instruction: str,
    language: str,
    persist_callback: Any = None,
) -> GameEvent:
    """Rewrite prose, regenerate matching options, then commit both together."""
    with _mutation_lock(loop):
        original = _require_current(loop).model_copy(deep=True)
        original_state = loop.player_state.model_copy(deep=True)
        try:
            rewritten = loop.ai_generator.rewrite_story_segment(
                full_story=full_story,
                segment_to_replace=segment_to_replace,
                user_instruction=user_instruction,
                character_settings=loop.player_state.character_settings,
                story_context=_daily_story_context(loop.player_state),
                language=language,
            )
            options_event = loop.ai_generator.generate_options_only(
                story_description=rewritten,
                player_state=loop.player_state.to_dict(),
                character_settings=loop.player_state.character_settings,
                language=language,
            )
            candidate = GameEvent(
                event_description=rewritten,
                options=[option.model_copy(deep=True) for option in options_event.options],
            )
            return _commit_candidate(
                loop, original, candidate, persist_callback=persist_callback
            )
        except Exception:
            _restore_state(loop, original_state, original)
            raise


def _daily_story_context(player_state: Any) -> str:
    records = getattr(player_state, "day_history", [])[-5:]
    return "\n".join(
        str(record.get("event_description") or record.get("summary") or "")
        for record in records
        if isinstance(record, dict)
    )
