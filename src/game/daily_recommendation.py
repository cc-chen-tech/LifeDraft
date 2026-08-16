"""Daily recommendation normalization without an additional model call."""

from __future__ import annotations

import re
from typing import Any, Iterable

from src.ai.models import EventOption
from src.game.daily_timeline import is_daily_timeline


def _state_value(state: Any, name: str, default: Any = None) -> Any:
    if isinstance(state, dict):
        return state.get(name, default)
    return getattr(state, name, default)


def _alignment_tokens(text: str) -> set[str]:
    lowered = text.casefold()
    words = set(re.findall(r"[a-z0-9]+", lowered))
    chinese = [char for char in lowered if "\u4e00" <= char <= "\u9fff"]
    return words | set(chinese)


def _alignment_score(option: EventOption, state: Any) -> tuple[int, int]:
    vision = str(_state_value(state, "life_vision", "") or "")
    settings = _state_value(state, "character_settings", {}) or {}
    conflict = ""
    if isinstance(settings, dict):
        conflict = str(
            settings.get("core_conflict")
            or settings.get("conflict")
            or settings.get("life_conflict")
            or ""
        )
    anchors = _alignment_tokens(f"{vision} {conflict}")
    overlap = len(anchors & _alignment_tokens(option.text))
    return overlap, -len(option.text)


def prepare_daily_option_recommendation(
    options: Iterable[EventOption], state: Any
) -> list[EventOption]:
    """Return options with exactly one daily recommendation.

    A valid model-authored recommendation is preserved. Missing flags are
    repaired locally using vision/conflict overlap; multiple flags keep the
    first model choice so recovery is deterministic.
    """

    prepared = [option.model_copy(deep=True) for option in options]
    if not is_daily_timeline(state) or not prepared:
        return prepared

    selected = [index for index, option in enumerate(prepared) if option.likely_choice]
    if len(selected) == 1:
        return prepared
    if selected:
        recommended_index = selected[0]
    else:
        recommended_index = max(
            range(len(prepared)),
            key=lambda index: (_alignment_score(prepared[index], state), -index),
        )
    for index, option in enumerate(prepared):
        option.likely_choice = index == recommended_index
    return prepared
