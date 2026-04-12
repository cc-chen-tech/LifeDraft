"""Generation state machine for tracking story generation lifecycle.

Inspired by Claude Code's query loop state machine with transition tracking.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TransitionReason(str, Enum):
    """Reasons for state transitions during generation."""
    INITIAL = "initial"
    HARNESS_RETRY = "harness_retry"
    TEMPERATURE_ADJUST = "temperature_adjust"
    CONTEXT_COMPACT = "context_compact"
    TRUNCATION_RECOVERY = "truncation_recovery"
    MODEL_FALLBACK = "model_fallback"
    MAX_TOKENS_ESCALATE = "max_tokens_escalate"


@dataclass
class GenerationState:
    """Snapshot of the generation state at a point in time."""
    attempt: int
    transition_reason: TransitionReason
    temperature: float
    context_budget_factor: float
    model_used: str
    started_at: float = field(default_factory=time.time)
    metrics: Dict[str, Any] = field(default_factory=dict)


class StateTracker:
    """Tracks generation state transitions for debugging and metrics."""

    def __init__(self, initial_model: str = "", initial_temperature: float = 0.85) -> None:
        raise NotImplementedError

    def transition(self, reason: TransitionReason, **updates: Any) -> GenerationState:
        """Record a state transition.

        Args:
            reason: Why the transition occurred
            **updates: Fields to update (temperature, model_used, context_budget_factor, etc.)

        Returns:
            The new GenerationState after transition
        """
        raise NotImplementedError

    def current(self) -> GenerationState:
        """Return the current generation state."""
        raise NotImplementedError

    def to_metrics(self) -> Dict[str, Any]:
        """Export state history as metrics dict compatible with HarnessMetrics.

        Returns dict with keys: total_attempts, transitions, final_model,
        final_temperature, total_duration_ms, transition_reasons
        """
        raise NotImplementedError

    def history(self) -> List[GenerationState]:
        """Return full history of generation states."""
        raise NotImplementedError
