"""Resolve daily story generation requests from persisted event state."""

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional, Union

from pydantic import ValidationError

from src.ai.models import GameEvent


RequestedDailyIntent = Literal["ensure_current", "replace_current"]
ResolvedDailyMode = Literal[
    "return_existing",
    "generate_missing",
    "replace_current",
]
PersistedDailyEvent = Optional[Union[GameEvent, Mapping[str, Any]]]


@dataclass(frozen=True)
class DailyGenerationResolution:
    """The operation the backend should execute for the current save slot."""

    requested_intent: RequestedDailyIntent
    resolved_mode: ResolvedDailyMode
    base_event_id: str = ""
    base_revision: int = 0


def _validated_event(value: PersistedDailyEvent) -> Optional[GameEvent]:
    if isinstance(value, GameEvent):
        return value
    if not isinstance(value, Mapping):
        return None
    try:
        return GameEvent.model_validate(dict(value))
    except ValidationError:
        return None


def is_complete_daily_event(value: PersistedDailyEvent) -> bool:
    """Return whether a persisted value is a complete, playable daily story."""

    event = _validated_event(value)
    return bool(
        event
        and event.event_description.strip()
        and len(event.options) >= 2
        and all(option.text.strip() for option in event.options)
    )


def resolve_daily_generation_intent(
    requested_intent: RequestedDailyIntent,
    current_event: PersistedDailyEvent,
) -> DailyGenerationResolution:
    """Route ensure/replace requests without trusting the caller's endpoint choice."""

    if requested_intent not in ("ensure_current", "replace_current"):
        raise ValueError(f"Unsupported daily generation intent: {requested_intent}")

    event = _validated_event(current_event)
    if event is None or not is_complete_daily_event(event):
        return DailyGenerationResolution(
            requested_intent=requested_intent,
            resolved_mode="generate_missing",
        )

    resolved_mode: ResolvedDailyMode = (
        "return_existing"
        if requested_intent == "ensure_current"
        else "replace_current"
    )
    return DailyGenerationResolution(
        requested_intent=requested_intent,
        resolved_mode=resolved_mode,
        base_event_id=event.event_id,
        base_revision=event.revision,
    )
