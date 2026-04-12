"""Model fallback chain - auto-switch to backup models on failure.

Inspired by Claude Code's model degradation strategy.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple

if TYPE_CHECKING:
    from src.ai.client import AIClient

logger = logging.getLogger(__name__)


@dataclass
class ModelFallbackConfig:
    """Configuration for model fallback chain."""
    primary_model: str
    fallback_models: List[str]
    retry_on_status_codes: List[int] = field(default_factory=lambda: [429, 529, 503])
    max_fallback_attempts: int = 3


class FallbackChain:
    """Manages automatic model switching on API failures."""

    def __init__(self, config: ModelFallbackConfig, client: "AIClient") -> None:
        raise NotImplementedError

    def call_with_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> Tuple[str, str]:
        """Call AI with automatic model fallback.

        Returns:
            Tuple of (response_text, actual_model_used)
        """
        raise NotImplementedError

    def get_available_models(self) -> List[str]:
        """Return list of all configured models (primary + fallbacks)."""
        raise NotImplementedError
