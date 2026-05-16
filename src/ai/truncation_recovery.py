"""Output truncation detection and recovery.

Inspired by Claude Code's max_output_tokens escalation and multi-turn recovery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONTINUATION_PROMPT_ZH = (
    "请从中断处继续输出，不要重新开头，不要道歉，不要总结。直接续写内容。"
)
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
        self._config = config or TruncationRecoveryConfig()

    def detect_truncation(self, response: str, finish_reason: Optional[str]) -> bool:
        """Check if the response was truncated.

        Args:
            response: The generated text
            finish_reason: OpenAI finish_reason field ("stop", "length", etc.)

        Returns:
            True if truncation is detected
        """
        if finish_reason is None:
            return False
        if finish_reason == "length":
            return True
        # Heuristic: response ends with a CJK character but no terminal punctuation
        if response:
            last_char = response.rstrip()[-1:] if response.rstrip() else ""
            terminal_puncts = set("。！？.!?\"'）)】」』\n")
            if (
                last_char
                and "\u4e00" <= last_char <= "\u9fff"
                and last_char not in terminal_puncts
            ):
                return True
        return False

    def build_continuation_prompt(
        self, original_prompt: str, partial_response: str, language: str = "zh"
    ) -> str:
        """Build a prompt to continue from truncation point."""
        tail = (
            partial_response[-500:] if len(partial_response) > 500 else partial_response
        )
        continuation_instruction = (
            self._config.continuation_prompt_zh
            if language == "zh"
            else self._config.continuation_prompt_en
        )
        prompt = (
            f"以下是之前的输出（已被截断）:\n\n...{tail}\n\n{continuation_instruction}"
        )
        return prompt

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
        full_text = partial_response
        terminal_puncts = set("。！？.!?")

        for i in range(self._config.max_continuations):
            logger.info(
                "Truncation recovery: continuation attempt %d/%d",
                i + 1,
                self._config.max_continuations,
            )
            continuation_prompt = self.build_continuation_prompt(
                original_prompt, full_text, language
            )
            # Remove stream_callback for continuation calls
            kwargs = {k: v for k, v in call_kwargs.items() if k != "stream_callback"}
            continuation_text: str = client_call(
                system_prompt=system_prompt,
                user_prompt=continuation_prompt,
                **kwargs,
            )
            full_text += continuation_text
            # Check if continuation ends with a complete sentence
            stripped = continuation_text.rstrip()
            if stripped and stripped[-1] in terminal_puncts:
                logger.info(
                    "Truncation recovery: complete sentence detected, stopping."
                )
                break

        return full_text
