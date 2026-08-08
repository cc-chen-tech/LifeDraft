"""Canonical effect normalization for resources and relationship deltas."""

from typing import Any, Dict

RESOURCE_EFFECT_KEYS = ("energy", "mood", "knowledge")


def normalize_resource_effects(effects: Any) -> Dict[str, int]:
    """Keep only integer deltas for the three public resources."""
    if not isinstance(effects, dict):
        return {}
    return {
        key: value
        for key in RESOURCE_EFFECT_KEYS
        if isinstance((value := effects.get(key)), int)
        and not isinstance(value, bool)
    }


def normalize_relationship_effects(value: Any) -> Dict[str, int]:
    """Validate relationship deltas independently from public resources."""
    if not isinstance(value, dict):
        return {}
    return {
        name.strip(): delta
        for name, delta in value.items()
        if isinstance(name, str)
        and name.strip()
        and isinstance(delta, int)
        and not isinstance(delta, bool)
    }


def normalize_gameplay_effects(effects: Any) -> Dict[str, Any]:
    """Keep public resources plus the separate relationship-effect structure."""
    normalized: Dict[str, Any] = dict(normalize_resource_effects(effects))
    if not isinstance(effects, dict):
        return normalized
    relationships = normalize_relationship_effects(
        effects.get("relationships")
    )
    if relationships:
        normalized["relationships"] = relationships
    return normalized
