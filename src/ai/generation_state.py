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
        self._history: List[GenerationState] = []
        self._start_time = time.time()
        initial_state = GenerationState(
            attempt=0,
            transition_reason=TransitionReason.INITIAL,
            temperature=initial_temperature,
            context_budget_factor=1.0,
            model_used=initial_model,
            started_at=self._start_time,
        )
        self._history.append(initial_state)

    def transition(self, reason: TransitionReason, **updates: Any) -> GenerationState:
        """Record a state transition.

        Args:
            reason: Why the transition occurred
            **updates: Fields to update (temperature, model_used, context_budget_factor, etc.)

        Returns:
            The new GenerationState after transition
        """
        cur = self._history[-1]
        new_attempt = cur.attempt + 1 if reason == TransitionReason.HARNESS_RETRY else cur.attempt
        new_state = GenerationState(
            attempt=new_attempt,
            transition_reason=reason,
            temperature=updates.get("temperature", cur.temperature),
            context_budget_factor=updates.get("context_budget_factor", cur.context_budget_factor),
            model_used=updates.get("model_used", cur.model_used),
            started_at=time.time(),
            metrics=updates.get("metrics", {}),
        )
        self._history.append(new_state)
        logger.debug("State transition: %s -> attempt=%d", reason.value, new_state.attempt)
        return new_state

    def current(self) -> GenerationState:
        """Return the current generation state."""
        return self._history[-1]

    def to_metrics(self) -> Dict[str, Any]:
        """Export state history as metrics dict compatible with HarnessMetrics.

        Returns dict with keys: total_attempts, transitions, final_model,
        final_temperature, total_duration_ms, transition_reasons
        """
        final = self._history[-1]
        return {
            "total_attempts": len(self._history),
            "transitions": [
                {
                    "reason": s.transition_reason.value,
                    "attempt": s.attempt,
                    "temperature": s.temperature,
                }
                for s in self._history
            ],
            "final_model": final.model_used,
            "final_temperature": final.temperature,
            "total_duration_ms": (time.time() - self._start_time) * 1000,
            "transition_reasons": [s.transition_reason.value for s in self._history],
        }

    def history(self) -> List[GenerationState]:
        """Return full history of generation states."""
        return list(self._history)
