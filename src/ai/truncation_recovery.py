"""Output truncation detection and recovery.

Inspired by Claude Code's max_output_tokens escalation and multi-turn recovery.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONTINUATION_PROMPT_ZH = "请从中断处继续输出，不要重新开头，不要道歉，不要总结。直接续写内容。"
DEFAULT_CONTINUATION_PROMPT_EN = "Continue output from where it was cut off. Do not restart, apologize, or summarize. Continue writing directly."


@dataclass
class TruncationRecoveryConfig:
    """Configuration for truncation recovery."""
    max_continuations: int = 3
    continuation_prompt_zh: str = DEFAULT_CONTINUATION_PROMPT_ZH
    continuation_prompt_en: str = DEFAULT_CONTINUATION_PROMPT_EN


class TruncationRecovery:
    """Detects output truncation and automatically continues generation."""

    def __init__(self, config: Optional[TruncationRecoveryConfig] = None) -> None:
        raise NotImplementedError

    def detect_truncation(self, response: str, finish_reason: Optional[str]) -> bool:
        """Check if the response was truncated.

        Args:
            response: The generated text
            finish_reason: OpenAI finish_reason field ("stop", "length", etc.)

        Returns:
            True if truncation is detected
        """
        raise NotImplementedError

    def build_continuation_prompt(
        self, original_prompt: str, partial_response: str, language: str = "zh"
    ) -> str:
        """Build a prompt to continue from truncation point."""
        raise NotImplementedError

    def recover(
        self,
        client_call: Callable[..., str],
        system_prompt: str,
        original_prompt: str,
        partial_response: str,
        language: str = "zh",
        **call_kwargs: Any,
    ) -> str:
        """Attempt to recover from truncation by issuing continuation calls.

        Returns:
            Complete text (original partial + all continuations joined)
        """
        raise NotImplementedError
