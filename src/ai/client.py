"""Unified AI calling abstraction layer.

All AI services depend on this client instead of directly accessing
OpenAI SDK or private methods. This ensures:
1. Single point of control for all AI calls
2. Consistent error handling and retry logic
3. Error feedback injection on retries (building-agents best practice)
4. Easy to swap underlying provider
"""

import logging
import re
from typing import Any, Callable, Dict, Optional

import openai

from config.settings import settings
from src.ai.utils import extract_json

logger = logging.getLogger(__name__)

# ★ max_tokens 自动降级配置
MAX_TOKENS_FALLBACK_LEVELS = [8000, 6000, 4000]  # 降级序列


def _is_max_tokens_error(error_message: str) -> bool:
    """检查是否为 max_tokens 相关错误"""
    patterns = [
        r"Invalid max_tokens value",
        r"max_tokens.*valid range",
        r"max_tokens.*out of range",
        r"token.*limit.*exceeded",
    ]
    return any(re.search(p, error_message, re.IGNORECASE) for p in patterns)


class AIClient:
    """Base AI calling abstraction. All AI services depend on this."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize the AI client.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: OpenAI model name (defaults to settings)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL

        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        client_kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if settings.OPENAI_BASE_URL:
            client_kwargs["base_url"] = settings.OPENAI_BASE_URL

        self.client = openai.OpenAI(**client_kwargs)

    # -------------------- Core Call --------------------

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        stream_callback: Optional[Callable[[str], None]] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Unified AI call method.

        Args:
            system_prompt: System prompt text
            user_prompt: User prompt text
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            stream_callback: Optional streaming callback
            model: Optional model override

        Returns:
            AI generated text
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        use_model = model or self.model

        # ★ max_tokens 自动降级重试逻辑
        current_max_tokens = max_tokens
        fallback_tokens = [t for t in MAX_TOKENS_FALLBACK_LEVELS if t < max_tokens]
        tokens_to_try = [max_tokens] + fallback_tokens

        last_error = None
        for attempt, current_max_tokens in enumerate(tokens_to_try):
            try:
                if stream_callback:
                    logger.info(
                        f"[AIClient] Using streaming mode, stream_callback={stream_callback is not None}"
                    )
                    stream = self.client.chat.completions.create(
                        model=use_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=current_max_tokens,
                        stream=True,
                    )

                    full_text = ""
                    finish_reason = None
                    chunk_count = 0
                    for chunk in stream:
                        if chunk.choices[0].delta.content is not None:
                            chunk_text = chunk.choices[0].delta.content
                            full_text += chunk_text
                            chunk_count += 1
                            stream_callback(chunk_text)
                        if chunk.choices[0].finish_reason:
                            finish_reason = chunk.choices[0].finish_reason
                    logger.info(
                        f"[AIClient] Streaming complete: {chunk_count} chunks, {len(full_text)} chars"
                    )

                    if finish_reason == "length":
                        logger.warning(
                            f"⚠️ AI response truncated by max_tokens ({current_max_tokens}). "
                            f"Output length: {len(full_text)} chars. "
                            f"Consider increasing max_tokens."
                        )

                    return full_text.strip()
                else:
                    response = self.client.chat.completions.create(
                        model=use_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=current_max_tokens,
                    )

                    finish_reason = response.choices[0].finish_reason
                    if finish_reason == "length":
                        logger.warning(
                            f"⚠️ AI response truncated by max_tokens ({current_max_tokens}). "
                            f"Output length: {len(response.choices[0].message.content)} chars. "
                            f"Consider increasing max_tokens."
                        )

                    return response.choices[0].message.content.strip()

            except Exception as e:
                error_msg = str(e)
                last_error = e

                # ★ 检查是否为 max_tokens 错误，如果是则尝试降级
                if _is_max_tokens_error(error_msg):
                    if attempt < len(tokens_to_try) - 1:
                        next_tokens = tokens_to_try[attempt + 1]
                        logger.warning(
                            f"⚠️ max_tokens={current_max_tokens} failed, "
                            f"retrying with max_tokens={next_tokens}. Error: {error_msg[:100]}"
                        )
                        continue
                    else:
                        logger.error(f"All max_tokens fallback levels failed: {error_msg}")
                else:
                    # 非 max_tokens 错误，直接抛出
                    raise

        # 所有尝试都失败，抛出最后一个错误
        raise last_error

    # -------------------- JSON Call --------------------

    def call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        model: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Call AI and parse response as JSON.

        Args:
            system_prompt: System prompt text
            user_prompt: User prompt text
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            model: Optional model override

        Returns:
            Parsed JSON dict, or None if extraction fails
        """
        content = self.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )
        return extract_json(content)

    # -------------------- Retry with Error Feedback --------------------

    def call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        retry_count: int = 3,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        stream_callback: Optional[Callable[[str], None]] = None,
        model: Optional[str] = None,
        language: str = "zh",
    ) -> str:
        """
        Call AI with retry and error feedback injection.

        On retry, injects the previous error message into the prompt
        so the model can learn from its mistake and avoid repeating it.

        Args:
            system_prompt: System prompt text
            user_prompt: User prompt text
            retry_count: Number of retries
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            stream_callback: Optional streaming callback (only used on first attempt)
            model: Optional model override
            language: Language code for error feedback message

        Returns:
            AI generated text

        Raises:
            ValueError: If all retries fail
        """
        last_error: Optional[str] = None

        for attempt in range(retry_count):
            try:
                prompt = user_prompt
                if attempt > 0 and last_error:
                    if language == "zh":
                        feedback = (
                            f"\n\n【上次生成失败，原因：{last_error}。"
                            f"请避免同样的问题，确保输出格式正确。】"
                        )
                    else:
                        feedback = (
                            f"\n\n[Previous generation failed. Reason: {last_error}. "
                            f"Please avoid the same issue and ensure correct output format.]"
                        )
                    prompt = user_prompt + feedback

                # Only use stream_callback on first attempt
                cb = stream_callback if attempt == 0 else None

                return self.call(
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream_callback=cb,
                    model=model,
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(f"AI call attempt {attempt + 1}/{retry_count} failed: {e}")
                if attempt == retry_count - 1:
                    raise ValueError(f"AI call failed after {retry_count} attempts: {e}")

        raise ValueError("AI call failed after all retries")
