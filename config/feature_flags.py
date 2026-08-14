"""Unified feature flag system.

Inspired by Claude Code's feature() gate pattern. Centralizes all
experimental feature toggles with environment variable mapping.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Dict

from typing_extensions import TypedDict

logger = logging.getLogger(__name__)


class FeatureFlags(TypedDict, total=False):
    """All available feature flags."""
    constraint_harness: bool
    narrative_style_engine: bool
    creative_enhancement: bool
    epic_narrative: bool
    model_fallback: bool
    truncation_recovery: bool
    reactive_compression: bool
    parallel_postprocessing: bool
    generation_state_tracking: bool
    story_voice_reading: bool
    soft_narrative_lengths: bool
    unified_narrative_budgets: bool
    structured_story_memory: bool
    daily_timeline_v2: bool


# Mapping from feature flag name -> environment variable name
_ENV_VAR_MAP: Dict[str, str] = {
    "constraint_harness": "ENABLE_CONSTRAINT_HARNESS",
    "narrative_style_engine": "ENABLE_NARRATIVE_STYLE_ENGINE",
    "creative_enhancement": "ENABLE_CREATIVE_ENHANCEMENT",
    "epic_narrative": "ENABLE_EPIC_NARRATIVE",
    "model_fallback": "ENABLE_MODEL_FALLBACK",
    "truncation_recovery": "ENABLE_TRUNCATION_RECOVERY",
    "reactive_compression": "ENABLE_REACTIVE_COMPRESSION",
    "parallel_postprocessing": "ENABLE_PARALLEL_POSTPROCESSING",
    "generation_state_tracking": "ENABLE_GENERATION_STATE_TRACKING",
    "story_voice_reading": "ENABLE_STORY_VOICE_READING",
    "soft_narrative_lengths": "ENABLE_SOFT_NARRATIVE_LENGTHS",
    "unified_narrative_budgets": "ENABLE_UNIFIED_NARRATIVE_BUDGETS",
    "structured_story_memory": "ENABLE_STRUCTURED_STORY_MEMORY",
    "daily_timeline_v2": "ENABLE_DAILY_TIMELINE_V2",
}

FEATURE_DEFAULTS: FeatureFlags = {
    "constraint_harness": False,
    "narrative_style_engine": False,
    "creative_enhancement": False,
    "epic_narrative": False,
    "model_fallback": False,
    "truncation_recovery": False,
    "reactive_compression": False,
    "parallel_postprocessing": False,
    "generation_state_tracking": False,
    "story_voice_reading": True,
    "soft_narrative_lengths": False,
    "unified_narrative_budgets": False,
    "structured_story_memory": False,
    "daily_timeline_v2": False,
}


# Module-level override storage (for testing)
_overrides: Dict[str, bool] = {}
_lock = threading.Lock()


def get_feature(name: str) -> bool:
    """Get the current value of a feature flag.

    Priority: override > environment variable > default
    """
    # 1. Check overrides
    with _lock:
        if name in _overrides:
            return _overrides[name]

    # 2. Check environment variable
    env_var = _ENV_VAR_MAP.get(name)
    if env_var is not None:
        env_val = os.environ.get(env_var)
        if env_val is not None:
            return env_val.lower() in ("true", "1", "yes")

    # 3. Return default (False for unknown flags)
    default: bool = bool(FEATURE_DEFAULTS.get(name, False))
    return default


def set_feature(name: str, value: bool) -> None:
    """Override a feature flag value (for testing only)."""
    with _lock:
        _overrides[name] = value


def reset_features() -> None:
    """Reset all feature flag overrides (for testing only)."""
    with _lock:
        _overrides.clear()


def get_all_features() -> FeatureFlags:
    """Return current state of all feature flags."""
    result: Dict[str, bool] = {}
    for name in FEATURE_DEFAULTS:
        result[name] = get_feature(name)
    return FeatureFlags(**result)  # type: ignore
