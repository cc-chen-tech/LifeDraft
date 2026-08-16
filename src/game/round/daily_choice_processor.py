"""Atomic, model-free choice settlement for daily timeline games."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import logging
from threading import Lock
from typing import Any, Callable, Dict, Optional

from config.settings import settings
from src.ai.models import GameEvent
from src.game.continuity_ledger import ContinuityLedger
from src.game.daily_timeline import advance_daily_timeline, normalize_daily_timeline
from src.game.daily_transition import resolve_daily_transition
from src.game.world_projection_schema import compute_projection_source_hash
from src.game.world_projection_state import apply_world_projection_patch


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DailyChoiceProjection:
    """Pure projected settlement used by speculative generation."""

    state: Any
    result: Dict[str, Any]
    record: Dict[str, Any]


class DailyChoiceProcessor:
    """Validate and atomically settle one generated option for one story day."""

    def __init__(
        self,
        *,
        player_state_getter: Callable[[], Any],
        current_event_getter: Callable[[], Optional[GameEvent]],
        current_event_setter: Callable[[Optional[GameEvent]], None],
        result_callback: Optional[Callable[[Dict[str, Any], Any], None]] = None,
        postprocess_callback: Optional[Callable[[str], None]] = None,
        settlement_lock: Optional[Any] = None,
        language_getter: Optional[Callable[[], str]] = None,
        projection_lookup: Optional[Callable[..., Any]] = None,
        projection_settled_callback: Optional[Callable[[Any], None]] = None,
    ) -> None:
        self._get_player_state = player_state_getter
        self._get_current_event = current_event_getter
        self._set_current_event = current_event_setter
        self.result_callback = result_callback
        self.postprocess_callback = postprocess_callback
        self._settlement_lock = settlement_lock or Lock()
        self._get_language = language_getter or (lambda: "zh")
        self.projection_lookup = projection_lookup
        self.projection_settled_callback = projection_settled_callback

    def make_choice(
        self,
        *,
        event_id: str,
        revision: int,
        option_index: int,
        persist_callback: Optional[Callable[[Any], bool]] = None,
        prefetched_event: Optional[GameEvent] = None,
    ) -> Dict[str, Any]:
        # Serialize settlement for one live game loop. Without this lock two
        # concurrent requests could both validate the same revision and persist
        # different choices before either swaps the committed state in memory.
        with self._settlement_lock:
            return self._make_choice_locked(
                event_id=event_id,
                revision=revision,
                option_index=option_index,
                persist_callback=persist_callback,
                prefetched_event=prefetched_event,
            )

    def _make_choice_locked(
        self,
        *,
        event_id: str,
        revision: int,
        option_index: int,
        persist_callback: Optional[Callable[[Any], bool]],
        prefetched_event: Optional[GameEvent],
    ) -> Dict[str, Any]:
        state = self._get_player_state()
        if state is None:
            raise ValueError("Game not started.")
        if not event_id or revision < 1:
            raise ValueError("missing_event_version")

        duplicate = self._find_duplicate(state, event_id, revision, option_index)
        if duplicate is not None:
            return duplicate

        event = self._get_current_event()
        if event is None:
            raise ValueError("No current event. Generate a daily event first.")
        if event.event_id != event_id:
            raise ValueError("stale_event_id")
        if event.revision != revision:
            raise ValueError("stale_event_revision")
        if option_index < 0 or option_index >= len(event.options):
            raise ValueError(f"Invalid option index: {option_index}")

        timeline = normalize_daily_timeline(state.timeline)
        if event.story_date and event.story_date != timeline["current_date"]:
            raise ValueError("stale_story_date")

        option = event.options[option_index]
        projection_identity = {
            "event_id": event.event_id,
            "revision": event.revision,
            "day_index": timeline["day_index"],
            "source_hash": compute_projection_source_hash(
                event.event_description, event.options
            ),
        }
        projection = self._lookup_projection(projection_identity)
        transition_text = resolve_daily_transition(
            option,
            state,
            option_index=option_index,
            language=self._get_language(),
        )
        requested = deepcopy(option.effects)
        applied, warnings = self._normalize_effects(state, requested)
        staged = state.model_copy(deep=True)

        # Wealth was removed from the canonical state on main. Ignore legacy
        # option payloads instead of reviving the retired financial ledger.
        applied.pop("wealth", None)
        requested.pop("wealth", None)
        staged.update(
            energy=applied.get("energy"),
            mood=applied.get("mood"),
            knowledge=applied.get("knowledge"),
            relationships=applied.get("relationships"),
        )

        completed_day_number = timeline["day_number"]
        weekly_decay = completed_day_number % 7 == 0
        if weekly_decay:
            staged.update(mood=-2)

        next_timeline = advance_daily_timeline(staged.__dict__)
        summary_milestones = []
        if completed_day_number % 365 == 0:
            summary_milestones.append("yearly")
        elif completed_day_number % 28 == 0:
            summary_milestones.append("long_term")
        record = {
            "event_id": event.event_id,
            "revision": event.revision,
            "day_index": timeline["day_index"],
            "story_date": timeline["current_date"],
            "event_description": event.event_description,
            "options": [item.model_dump() for item in event.options],
            "choice_option_index": option_index,
            "choice": option.text,
            "recommended_option_index": next(
                (
                    index
                    for index, candidate in enumerate(event.options)
                    if candidate.likely_choice
                ),
                None,
            ),
            "recommendation_selected": bool(option.likely_choice),
            "transition_text": transition_text,
            "effects_requested": requested,
            "effects_applied": deepcopy(applied),
            "resource_warnings": warnings,
            "postprocessing_status": "pending",
            "summary_milestones": summary_milestones,
            "world_projection_identity": deepcopy(projection_identity),
            "world_projection_status": "pending",
        }
        projection_id = self._matching_projection_id(projection, projection_identity)
        if projection_id is not None:
            record["world_projection_id"] = projection_id
        result = {
            "story_continuation": "",
            "summary": "",
            "transition_text": transition_text,
            "effects_applied": deepcopy(applied),
            "effects_requested": requested,
            "resource_warnings": warnings,
            "need_weekly_summary": False,
            "weekly_summary": None,
            "weekly_decay_applied": weekly_decay,
            "summary_milestones": summary_milestones,
            "next_timeline": deepcopy(next_timeline),
            "game_over": bool(next_timeline.get("game_over")),
            "prefetch_hit": False,
        }
        promoted_event = None
        if (
            prefetched_event is not None
            and prefetched_event.story_date == next_timeline.get("current_date")
        ):
            promoted_event = prefetched_event.model_copy(deep=True)
            result["prefetch_hit"] = True
        record["choice_result"] = deepcopy(result)
        staged.day_history.append(record)
        if projection_id is not None and str(
            self._projection_field(projection, "status") or ""
        ) in {"ready", "ready_no_change", "applied"}:
            try:
                apply_world_projection_patch(staged, projection, option_index)
            except Exception:
                # A projection is derived, repairable state.  Even a ready row
                # can be temporarily inapplicable when an older day is still a
                # gap, so it must never turn a valid player choice into a hard
                # failure.  The serial applier will retry after the gap closes.
                logger.exception(
                    "daily world projection apply deferred event_id=%s revision=%s",
                    event.event_id,
                    event.revision,
                )
            else:
                record["world_projection_status"] = "applied"
        ledger_fact_updates = []
        for name, change in (applied.get("relationships") or {}).items():
            ledger_fact_updates.append(
                {
                    "action": "update",
                    "subject": str(name),
                    "category": "relationship",
                    "fact": (
                        f"与主角的关系变动 {int(change):+d}，"
                        f"当前亲密度 {staged.relationships.get(str(name), 50)}"
                    ),
                }
            )
        ledger = ContinuityLedger.from_player_state(staged)
        ledger.record_committed_event(
            event_id=event.event_id,
            week=timeline["week_number"] - 1,
            round_number=(timeline["day_number"] - 1) % 7,
            date_info={
                "story_date": timeline["current_date"],
                "day_index": timeline["day_index"],
                "day_number": timeline["day_number"],
            },
            summary=event.event_description[:200],
            choice=option.text,
            story_text=event.event_description,
            fact_updates=ledger_fact_updates,
        )
        ledger.persist(staged)
        staged.current_event_data = (
            promoted_event.model_dump() if promoted_event is not None else None
        )
        staged.resume_view = None

        # Persist the staged candidate before exposing it in memory. A failed
        # save leaves the current event and all resources untouched, while a
        # process crash after the durable write safely restores the advanced day.
        if persist_callback is not None and not persist_callback(staged):
            raise RuntimeError("daily_choice_persistence_failed")

        # All validation and settlement happens on a deep copy. After the
        # durable write, this field swap publishes the same candidate in memory.
        for field_name in type(state).model_fields:
            setattr(state, field_name, deepcopy(getattr(staged, field_name)))
        self._set_current_event(promoted_event)
        if self.result_callback:
            self.result_callback(result, state)
        if self.postprocess_callback:
            self.postprocess_callback(event_id)
        if self.projection_settled_callback:
            try:
                self.projection_settled_callback(projection)
            except Exception:
                logger.exception(
                    "daily world projection settlement wake failed event_id=%s",
                    event_id,
                )
        return result

    def _lookup_projection(self, identity: Dict[str, Any]) -> Any:
        if self.projection_lookup is None:
            return None
        try:
            return self.projection_lookup(**identity)
        except Exception:
            logger.exception(
                "daily world projection lookup failed event_id=%s revision=%s",
                identity["event_id"],
                identity["revision"],
            )
            return None

    @staticmethod
    def _projection_field(value: Any, name: str) -> Any:
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    @classmethod
    def _matching_projection_id(
        cls, projection: Any, identity: Dict[str, Any]
    ) -> Optional[int]:
        if projection is None or any(
            cls._projection_field(projection, name) != expected
            for name, expected in identity.items()
        ):
            return None
        projection_id = cls._projection_field(projection, "projection_id")
        if isinstance(projection_id, bool) or not isinstance(projection_id, int):
            return None
        return projection_id

    def _find_duplicate(
        self, state: Any, event_id: str, revision: int, option_index: int
    ) -> Optional[Dict[str, Any]]:
        for record_position in range(len(state.day_history) - 1, -1, -1):
            record = state.day_history[record_position]
            if record.get("event_id") != event_id:
                continue
            if (
                record.get("revision") == revision
                and record.get("choice_option_index") == option_index
            ):
                saved = record.get("choice_result")
                if isinstance(saved, dict):
                    restored = deepcopy(saved)
                    if not restored.get("transition_text"):
                        raw_options = record.get("options")
                        if isinstance(raw_options, list) and option_index < len(
                            raw_options
                        ):
                            try:
                                from src.ai.models import EventOption

                                option = EventOption(**raw_options[option_index])
                                fallback_state = {
                                    "timeline": {
                                        "version": 2,
                                        "day_index": int(record.get("day_index") or 0),
                                    },
                                    "day_history": state.day_history[:record_position],
                                }
                                restored["transition_text"] = resolve_daily_transition(
                                    option,
                                    fallback_state,
                                    option_index=option_index,
                                    language=self._get_language(),
                                )
                            except (TypeError, ValueError, IndexError):
                                pass
                    return restored
            raise ValueError("event_already_settled")
        return None

    @staticmethod
    def _normalize_effects(
        state: Any, requested: Dict[str, Any]
    ) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
        applied = deepcopy(requested)
        warnings = []
        for key, current, lower, upper in (
            ("energy", state.energy, settings.MIN_RESOURCE, settings.MAX_RESOURCE),
            ("mood", state.mood, settings.MIN_RESOURCE, settings.MAX_RESOURCE),
            (
                "knowledge",
                state.knowledge,
                settings.MIN_RESOURCE,
                settings.MAX_RESOURCE,
            ),
        ):
            if key not in requested:
                continue
            delta = requested[key]
            if isinstance(delta, bool) or not isinstance(delta, int):
                raise ValueError(f"invalid_effect:{key}")
            target = max(lower, current + delta)
            if upper is not None:
                target = min(upper, target)
            actual = target - current
            applied[key] = actual
            if actual != delta:
                warnings.append(
                    {
                        "resource": key,
                        "requested_delta": delta,
                        "applied_delta": actual,
                        "reason": (
                            "insufficient_resource" if delta < 0 else "resource_cap"
                        ),
                    }
                )
        relationships = requested.get("relationships")
        if relationships is not None:
            if not isinstance(relationships, dict) or any(
                isinstance(change, bool) or not isinstance(change, int)
                for change in relationships.values()
            ):
                raise ValueError("invalid_effect:relationships")
        return applied, warnings


def project_daily_choice(
    state: Any,
    event: GameEvent,
    *,
    option_index: int,
    language: str = "zh",
) -> DailyChoiceProjection:
    """Apply the canonical daily settlement to an isolated state clone."""

    projected_state = state.model_copy(deep=True)
    holder: Dict[str, Optional[GameEvent]] = {"event": event.model_copy(deep=True)}
    processor = DailyChoiceProcessor(
        player_state_getter=lambda: projected_state,
        current_event_getter=lambda: holder["event"],
        current_event_setter=lambda value: holder.__setitem__("event", value),
        language_getter=lambda: language,
    )
    result = processor.make_choice(
        event_id=event.event_id,
        revision=event.revision,
        option_index=option_index,
    )
    return DailyChoiceProjection(
        state=projected_state,
        result=deepcopy(result),
        record=deepcopy(projected_state.day_history[-1]),
    )
