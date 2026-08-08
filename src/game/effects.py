"""Canonical resource-effect normalization."""

from typing import Any, Dict

RESOURCE_EFFECT_KEYS = ("energy", "mood", "knowledge")


def normalize_resource_effects(effects: Any) -> Dict[str, int]:
    """Keep only integer deltas for the three public resources."""
    if not isinstance(effects, dict):
        return {}
    return {
        key: value
        for key in RESOURCE_EFFECT_KEYS
        if isinstance((value := effects.get(key)), int) and not isinstance(value, bool)
    }
