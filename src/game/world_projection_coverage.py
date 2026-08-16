"""Evidence-only detection for daily stories that require world projection."""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


_CATEGORY_TERMS = (
    (
        "location_updates",
        (
            "抵达",
            "到达",
            "前往",
            "来到",
            "离开",
            "搬到",
            "返回",
            "回到",
            "赶往",
            "进入",
        ),
    ),
    (
        "commitment_updates",
        ("承诺", "约定", "答应", "兑现", "履行", "完成", "取消", "失约"),
    ),
    (
        "fact_updates",
        ("受伤", "康复", "失去", "获得", "成为", "不再", "状态变为"),
    ),
    (
        "career_updates",
        ("入职", "升职", "晋升", "调任", "辞职", "被解雇", "换了工作"),
    ),
    (
        "habit_updates",
        ("养成了", "开始习惯", "不再习惯", "改掉了", "每天都会"),
    ),
)

_CAUSAL_RESOLUTION_TERMS = ("解决", "化解", "兑现", "后果", "结果", "因此", "导致")


@dataclass(frozen=True)
class WorldChangeSignals:
    """Matched evidence that extraction should have emitted a non-empty patch."""

    requires_nonempty_patch: bool
    categories: tuple[str, ...]
    matched_spans: tuple[str, ...]


def _tracked_character_names(tracked_state: Any) -> tuple[str, ...]:
    if not isinstance(tracked_state, Mapping):
        return ()
    locations = tracked_state.get("character_locations")
    if not isinstance(locations, Mapping):
        return ()
    return tuple(str(name) for name in locations if str(name).strip())


def _has_known_causal_chain(tracked_state: Any) -> bool:
    if not isinstance(tracked_state, Mapping):
        return False
    chains = tracked_state.get("causal_chains")
    return isinstance(chains, (Mapping, list, tuple)) and bool(chains)


def detect_world_change_signals(
    story: str,
    options: Sequence[Any],
    tracked_state: Any = None,
) -> WorldChangeSignals:
    """Detect evidence of movement, commitment lifecycle, or causal changes."""

    option_text = "\n".join(
        str(option.get("text") if isinstance(option, Mapping) else option or "")
        for option in options
    )
    text = f"{story or ''}\n{option_text}"
    tracked_names = _tracked_character_names(tracked_state)
    categories = []
    matches = []

    for category, terms in _CATEGORY_TERMS:
        if category == "location_updates":
            if not tracked_names or not any(name in text for name in tracked_names):
                continue
        category_matches = [term for term in terms if term in text]
        if not category_matches:
            continue
        categories.append(category)
        for term in category_matches:
            if term not in matches:
                matches.append(term)

    if _has_known_causal_chain(tracked_state):
        causal_matches = [term for term in _CAUSAL_RESOLUTION_TERMS if term in text]
        if causal_matches:
            categories.append("causal_updates")
            for term in causal_matches:
                if term not in matches:
                    matches.append(term)

    return WorldChangeSignals(
        requires_nonempty_patch=bool(categories),
        categories=tuple(categories),
        matched_spans=tuple(matches),
    )
