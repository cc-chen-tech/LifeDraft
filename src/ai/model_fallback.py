"""Model fallback chain - auto-switch to backup models on failure.

Inspired by Claude Code's model degradation strategy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple

try:
    import openai
except ImportError:  # pragma: no cover
    openai = None  # type: ignore[assignment]

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
        self._config = config
        self._client = client
        self._models: List[str] = [config.primary_model] + list(config.fallback_models)

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
        last_error: Optional[Exception] = None
        attempts = min(self._config.max_fallback_attempts, len(self._models))

        for i in range(attempts):
            current_model = self._models[i]
            try:
                response = self._client.call(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream_callback=stream_callback,
                    model=current_model,
                )
                return response, current_model
            except Exception as e:
                last_error = e
                # Check if this is a retryable API error
                status_code: Optional[int] = None
                if hasattr(e, "status_code"):
                    status_code = getattr(e, "status_code", None)

                is_retryable = (
                    openai is not None
                    and isinstance(e, openai.APIError)
                    and status_code is not None
                    and status_code in self._config.retry_on_status_codes
                )

                if is_retryable and i < attempts - 1:
                    next_model = self._models[i + 1]
                    logger.warning(
                        "Model %s failed with status %s, falling back to %s",
                        current_model,
                        status_code,
                        next_model,
                    )
                    if status_callback is not None:
                        status_callback("model_fallback")
                    continue

                # Non-retryable or last attempt – re-raise
                raise

        # Should not be reached, but satisfies the type checker
        raise last_error  # type: ignore[misc]

    def get_available_models(self) -> List[str]:
        """Return list of all configured models (primary + fallbacks)."""
        return [self._config.primary_model] + list(self._config.fallback_models)
