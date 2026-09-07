"""Shared semantic boundaries for collection entity categories."""

from typing import Optional

# These are intentionally small, high-confidence vocabulary entries.  They
# cover the mythic story entities observed in production without treating all
# Chinese names ending in a generic character as locations or objects.
KNOWN_ITEM_NAMES = frozenset(
    {
        "金箍棒",
        "天外石",
        "龙鳞",
        "玉简",
        "水珠",
        "青石",
        "帛书",
        "九环锡杖",
    }
)

KNOWN_LANDMARK_NAMES = frozenset(
    {
        "花果山",
        "东海",
        "东海龙宫",
        "西海",
        "水帘洞",
        "瑶池",
        "寒潭",
        "灌江口",
        "灵台方寸山",
        "天裂谷",
    }
)

# ``金纹`` and similar fragments are not people, but should not be promoted
# to an item unless a model explicitly supplies a valid item record.
KNOWN_NON_PERSON_NAMES = frozenset({"金纹"})
KNOWN_PERSON_FRAGMENT_SUFFIXES = ("下传", "上前", "转来", "照看")
KNOWN_ACTION_SUFFIXES = (
    "站",
    "坐",
    "扶",
    "握",
    "看",
    "问",
    "说",
    "道",
    "守",
    "来",
    "去",
    "立",
    "转",
    "照",
)


def classify_known_entity_name(name: str) -> Optional[str]:
    """Return a high-confidence category for a known name, if any."""

    normalized = str(name or "").strip()
    if normalized in KNOWN_ITEM_NAMES:
        return "item"
    if normalized in KNOWN_LANDMARK_NAMES:
        return "landmark"
    if normalized in KNOWN_NON_PERSON_NAMES:
        return "non_person"
    return None


def is_known_non_person_name(name: str) -> bool:
    return classify_known_entity_name(name) is not None


def is_known_person_fragment(name: str) -> bool:
    normalized = str(name or "").strip()
    return any(
        normalized.endswith(suffix) for suffix in KNOWN_PERSON_FRAGMENT_SUFFIXES
    ) or (
        len(normalized) >= 3
        and normalized.startswith("阿")
        and normalized.endswith(("照", "转", "立"))
    )


def is_invalid_character_name(
    name: str, known_person_names: tuple[str, ...] = ()
) -> bool:
    """Reject known objects/places and a known-person action fragment."""

    normalized = str(name or "").strip()
    if (
        not normalized
        or is_known_non_person_name(normalized)
        or is_known_person_fragment(normalized)
    ):
        return True
    return any(
        known_name
        and normalized.startswith(known_name)
        and len(normalized) == len(known_name) + 1
        and normalized.endswith(KNOWN_ACTION_SUFFIXES)
        for known_name in known_person_names
    )
