"""Output truncation detection and recovery.

Inspired by Claude Code's max_output_tokens escalation and multi-turn recovery.
"""

from __future__ import annotations

import logging
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.ai.budgets import GenerationBudgetError, GenerationCallTracker

logger = logging.getLogger(__name__)

DEFAULT_CONTINUATION_PROMPT_ZH = (
    "请从中断处继续输出，不要重新开头，不要道歉，不要总结。直接续写内容。"
)
DEFAULT_CONTINUATION_PROMPT_EN = "Continue output from where it was cut off. Do not restart, apologize, or summarize. Continue writing directly."

# ★ 软限制 cap：续写时 max_tokens 升级的上限。
# 比 max_tokens 默认值大，避免续写也立即被截断（陷入死循环）。
# 8k 是 deepseek 推荐的稳定上限，超过有概率触发 rate limit。
DEFAULT_CONTINUATION_MAX_TOKENS_CAP = 8000

# ★ 续写时 max_tokens 的放大倍数。
# 第一次续写用 1.5x（避免续写也被同样截断），后续轮次用同一值（保持稳定）。
DEFAULT_CONTINUATION_GROWTH_FACTOR = 1.5


@dataclass
class TruncationRecoveryConfig:
    """Configuration for truncation recovery."""

    max_continuations: int = 3
    continuation_prompt_zh: str = DEFAULT_CONTINUATION_PROMPT_ZH
    continuation_prompt_en: str = DEFAULT_CONTINUATION_PROMPT_EN
    continuation_max_tokens_cap: int = DEFAULT_CONTINUATION_MAX_TOKENS_CAP
    continuation_growth_factor: float = DEFAULT_CONTINUATION_GROWTH_FACTOR


class TruncationRecovery:
    """Detects output truncation and automatically continues generation.

    续写时把 max_tokens 提升到原值的 1.5x（封顶到 cap），保证续写不会立即
    被同样的限制再次截断——这是把"硬截断"变成"软限制"的关键。
    """

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
            if last_char and "\u4e00" <= last_char <= "\u9fff" and last_char not in terminal_puncts:
                return True
        return False

    def build_continuation_prompt(
        self, original_prompt: str, partial_response: str, language: str = "zh"
    ) -> str:
        """Build a prompt to continue from truncation point."""
        tail = partial_response[-500:] if len(partial_response) > 500 else partial_response
        continuation_instruction = (
            self._config.continuation_prompt_zh
            if language == "zh"
            else self._config.continuation_prompt_en
        )
        prompt = f"以下是之前的输出（已被截断）:\n\n...{tail}\n\n{continuation_instruction}"
        return prompt

    def _compute_continuation_max_tokens(
        self,
        original_max_tokens: Optional[int],
    ) -> Optional[int]:
        """Compute the max_tokens to use for a continuation call.

        升级原值的 growth_factor 倍，封顶到 cap。如果原值未知或已经超过 cap，
        直接用 cap。
        """
        if original_max_tokens is None:
            return self._config.continuation_max_tokens_cap
        grown = int(original_max_tokens * self._config.continuation_growth_factor)
        # 至少比原值大 256，避免持平
        grown = max(grown, original_max_tokens + 256)
        return min(grown, self._config.continuation_max_tokens_cap)

    def recover(
        self,
        client_call: Callable[..., str],
        system_prompt: str,
        original_prompt: str,
        partial_response: str,
        language: str = "zh",
        generation_tracker: Optional[GenerationCallTracker] = None,
        **call_kwargs: Any,
    ) -> str:
        """Attempt to recover from truncation by issuing continuation calls.

        Returns:
            Complete text (original partial + all continuations joined)
        """
        full_text = partial_response
        terminal_puncts = set("。！？.!?")
        # ★ 软限制：续写时升级 max_tokens，避免反复被同样的限制截断
        continuation_max_tokens = self._compute_continuation_max_tokens(
            call_kwargs.get("max_tokens")
        )

        recovery_scope = (
            generation_tracker.recovery_scope() if generation_tracker is not None else nullcontext()
        )
        with recovery_scope:
            for i in range(self._config.max_continuations):
                logger.info(
                    "Truncation recovery: continuation attempt %d/%d (max_tokens=%s)",
                    i + 1,
                    self._config.max_continuations,
                    continuation_max_tokens,
                )
                try:
                    if generation_tracker is not None:
                        generation_tracker.consume("prose")
                except GenerationBudgetError as exc:
                    logger.warning(
                        "Truncation recovery stopped by original request budget: %s",
                        exc,
                    )
                    break
                continuation_prompt = self.build_continuation_prompt(
                    original_prompt, full_text, language
                )
                # Remove stream_callback for continuation calls and prohibit re-entry.
                kwargs = {k: v for k, v in call_kwargs.items() if k != "stream_callback"}
                kwargs["_allow_truncation_recovery"] = False
                # ★ 软限制：续写用升级后的 max_tokens
                if continuation_max_tokens is not None:
                    kwargs["max_tokens"] = continuation_max_tokens
                if generation_tracker is not None:
                    kwargs["request_timeout"] = generation_tracker.cap_timeout(
                        kwargs.get("request_timeout")
                    )
                continuation_text: str = client_call(
                    system_prompt=system_prompt,
                    user_prompt=continuation_prompt,
                    **kwargs,
                )
                full_text += continuation_text
                # Check if continuation ends with a complete sentence
                stripped = continuation_text.rstrip()
                if stripped and stripped[-1] in terminal_puncts:
                    logger.info("Truncation recovery: complete sentence detected, stopping.")
                    break

        return full_text
