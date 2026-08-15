"""Validation and deterministic fallbacks for daily choice transitions."""

from __future__ import annotations

import re
from typing import Any, Iterable, List, Optional, Sequence

from src.ai.models import EventOption


_ZH_FALLBACKS: Sequence[str] = (
    "话音落下，未散的余韵正悄然走向明日。",
    "决定留在身后，新的晨光已在时间深处亮起。",
    "这一刻渐渐安静，明日的光已落在前路。",
    "余音慢慢沉静，时间轻轻翻向了新的一页。",
    "未尽的话留在原地，日子已缓缓迈向清晨。",
    "心绪尚未平复，远处的天光已替明日开场。",
    "这番取舍有了回声，而日历正无声翻页。",
    "目光从此刻移开时，新的一日已悄然临近。",
    "决定的余温仍在，时间却已把故事带向明日。",
    "沉默收拢了这一刻，下一页正随天光展开。",
    "今日的回声渐远，明日已从静处缓缓靠近。",
    "那份心意安静落定，时间随之走向新的一天。",
    "片刻之后风声渐轻，日子又向前走了一格。",
    "这一念被妥善收下，明日的门扉正缓缓开启。",
    "尚存的余韵没有消散，却已随时间越过今夜。",
    "此刻终于沉静下来，新的一天正从远处靠近。",
)

_EN_FALLBACKS: Sequence[str] = (
    "The choice settles quietly as tomorrow draws nearer.",
    "Its aftertaste lingers while the day turns forward.",
    "The moment grows still, and a new day approaches.",
    "What was decided remains as time opens the next page.",
    "The echo stays behind while morning edges closer.",
    "The thought settles, and time carries it toward tomorrow.",
    "The moment closes gently as another day comes into view.",
    "Its quiet weight remains while the calendar turns.",
    "The choice finds its place, and the next day draws near.",
    "The lingering feeling follows time into a new morning.",
    "The day releases its hold as the next one approaches.",
    "What remains unsaid grows quiet before another day.",
    "The moment recedes, leaving tomorrow just ahead.",
    "Its meaning lingers while time moves one day onward.",
    "The last echo softens as a new day begins to gather.",
    "The choice rests quietly on the threshold of tomorrow.",
)

_FORBIDDEN_ZH = (
    "选项",
    "你选择",
    "选择了",
    "精力",
    "情绪值",
    "学识",
    "关系值",
    "数值",
    "一定会",
    "必将",
)
_FORBIDDEN_EN = (
    "option",
    "you chose",
    "energy",
    "mood",
    "knowledge",
    "stat",
    "will certainly",
    "is guaranteed",
)
_NORMALIZE_RE = re.compile(r"[\s，。！？、,.!?;；:：—\-]+")
_NUMERIC_RE = re.compile(r"[0-9０-９%％+＋]")


def normalize_daily_transition(text: str) -> str:
    """Normalize formatting away for exact recent-use comparisons."""
    return _NORMALIZE_RE.sub("", str(text or "")).casefold()


def _state_value(state: Any, key: str, default: Any) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _recent_transition_keys(state: Any) -> set[str]:
    history = _state_value(state, "day_history", [])
    if not isinstance(history, list):
        return set()
    return {
        normalize_daily_transition(str(entry.get("transition_text") or ""))
        for entry in history[-12:]
        if isinstance(entry, dict) and entry.get("transition_text")
    }


def is_valid_daily_transition(
    text: Optional[str],
    *,
    language: str = "zh",
    recent_transitions: Iterable[str] = (),
) -> bool:
    """Return whether a transition satisfies the local display contract."""
    if not isinstance(text, str):
        return False
    candidate = text.strip()
    key = normalize_daily_transition(candidate)
    if not candidate or not key:
        return False
    recent_keys = {
        normalize_daily_transition(item) for item in recent_transitions if item
    }
    if key in recent_keys:
        return False
    if _NUMERIC_RE.search(candidate):
        return False

    forbidden = _FORBIDDEN_ZH if language == "zh" else _FORBIDDEN_EN
    lowered = candidate.casefold()
    if any(token.casefold() in lowered for token in forbidden):
        return False

    terminators = re.findall(r"[。！？.!?]", candidate)
    if len(terminators) > 1:
        return False
    if terminators and not re.search(r"[。！？.!?][”’\"']?$", candidate):
        return False

    if language == "zh":
        compact_length = len(re.sub(r"\s+", "", candidate))
        return 12 <= compact_length <= 28
    word_count = len(re.findall(r"\b[\w'-]+\b", candidate))
    return 5 <= word_count <= 18


def _fallback_transition(
    *,
    language: str,
    day_index: int,
    option_index: int,
    excluded_keys: set[str],
) -> str:
    pool = _ZH_FALLBACKS if language == "zh" else _EN_FALLBACKS
    start = (day_index * 3 + option_index) % len(pool)
    for offset in range(len(pool)):
        candidate = pool[(start + offset) % len(pool)]
        if normalize_daily_transition(candidate) not in excluded_keys:
            return candidate
    # The pool is larger than the 12-entry exclusion window. This is a guard
    # for corrupted histories that contain more data than the public contract.
    return pool[start]


def prepare_daily_option_transitions(
    options: Sequence[EventOption],
    player_state: Any,
    *,
    language: str = "zh",
) -> List[EventOption]:
    """Keep valid model prose and deterministically repair every daily option."""
    timeline = _state_value(player_state, "timeline", {})
    if not isinstance(timeline, dict) or timeline.get("version") != 2:
        return list(options)

    day_index = int(timeline.get("day_index") or 0)
    excluded = _recent_transition_keys(player_state)
    prepared: List[EventOption] = []
    for option_index, option in enumerate(options):
        candidate = option.transition_text
        if not is_valid_daily_transition(
            candidate,
            language=language,
            recent_transitions=excluded,
        ):
            candidate = _fallback_transition(
                language=language,
                day_index=day_index,
                option_index=option_index,
                excluded_keys=excluded,
            )
        prepared.append(option.model_copy(update={"transition_text": candidate}))
        excluded.add(normalize_daily_transition(str(candidate)))
    return prepared


def resolve_daily_transition(
    option: EventOption,
    player_state: Any,
    *,
    option_index: int,
    language: str = "zh",
) -> str:
    """Resolve the exact transition to persist when a daily choice settles."""
    timeline = _state_value(player_state, "timeline", {})
    day_index = int(timeline.get("day_index") or 0) if isinstance(timeline, dict) else 0
    excluded = _recent_transition_keys(player_state)
    if is_valid_daily_transition(
        option.transition_text,
        language=language,
        recent_transitions=excluded,
    ):
        return str(option.transition_text).strip()
    return _fallback_transition(
        language=language,
        day_index=day_index,
        option_index=option_index,
        excluded_keys=excluded,
    )
