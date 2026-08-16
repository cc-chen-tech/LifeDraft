"""Evidence-only detection for daily stories that require world projection."""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


_CATEGORY_TERMS = (
    (
        "location",
        ("抵达", "到达", "前往", "来到", "离开", "搬到", "返回", "回到", "赶往", "进入"),
    ),
    (
        "commitment",
        ("承诺", "约定", "答应", "兑现", "履行", "失约"),
    ),
    (
        "causal",
        ("因为", "因此", "导致", "结果", "于是", "从而", "后果", "缘由", "起因"),
    ),
)


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
        if category == "location" and tracked_names:
            if not any(name in text for name in tracked_names):
                continue
        category_matches = [term for term in terms if term in text]
        if not category_matches:
            continue
        categories.append(category)
        for term in category_matches:
            if term not in matches:
                matches.append(term)

    return WorldChangeSignals(
        requires_nonempty_patch=bool(categories),
        categories=tuple(categories),
        matched_spans=tuple(matches),
    )
