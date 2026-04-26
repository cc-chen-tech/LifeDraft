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
import threading
from typing import Any, Callable, Dict, List, Optional

import openai

from config.feature_flags import get_feature
from config.settings import settings
from src.ai.model_fallback import FallbackChain, ModelFallbackConfig
from src.ai.truncation_recovery import TruncationRecovery
from src.ai.utils import extract_json

logger = logging.getLogger(__name__)

# ★ max_tokens 自动降级配置
MAX_TOKENS_FALLBACK_LEVELS = [8000, 6000, 4000]  # 降级序列

# ★ 模型降级链默认备选模型
_DEFAULT_FALLBACK_MODELS: List[str] = [
    "deepseek-v4-flash",
    "deepseek-chat",
    "gpt-4o-mini",
]


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

    # C-04: 并发限制，最多5个并发AI调用
    _semaphore = threading.Semaphore(5)

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

        # ★ 添加超时设置，避免长时间请求导致连接错误
        client_kwargs["timeout"] = 300.0  # 5分钟超时，实体识别需要较长时间

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
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
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
            frequency_penalty: Penalize repeated tokens by frequency (0.0-2.0)
            presence_penalty: Penalize tokens that already appeared (0.0-2.0)

        Returns:
            AI generated text
        """
        # C-04: 使用信号量限制并发调用
        with self._semaphore:
            # ★ 模型降级链：开启时自动切换备选模型
            if get_feature("model_fallback"):
                return self._call_with_model_fallback(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream_callback=stream_callback,
                    model=model,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                )
            return self._call_impl(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                stream_callback=stream_callback,
                model=model,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )

    def _call_with_model_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        stream_callback: Optional[Callable[[str], None]] = None,
        model: Optional[str] = None,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
    ) -> str:
        """Call AI with automatic model fallback using FallbackChain config.

        Uses ModelFallbackConfig for configuration and iterates through
        available models on retryable API errors, calling _call_impl directly
        to avoid semaphore re-entry.
        """
        use_model = model or self.model
        fallback_models = [m for m in _DEFAULT_FALLBACK_MODELS if m != use_model]
        config = ModelFallbackConfig(
            primary_model=use_model,
            fallback_models=fallback_models,
        )
        chain = FallbackChain(config, self)
        models = chain.get_available_models()

        last_error: Optional[Exception] = None
        attempts = min(config.max_fallback_attempts, len(models))
        for i in range(attempts):
            current_model = models[i]
            try:
                return self._call_impl(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream_callback=stream_callback,
                    model=current_model,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                )
            except Exception as e:
                last_error = e
                status_code = getattr(e, "status_code", None)
                is_retryable = (
                    isinstance(e, openai.APIError)
                    and status_code is not None
                    and status_code in config.retry_on_status_codes
                )
                if is_retryable and i < attempts - 1:
                    next_model = models[i + 1]
                    logger.warning(
                        "Model %s failed (status %s), falling back to %s",
                        current_model,
                        status_code,
                        next_model,
                    )
                    # Clear stream_callback for fallback attempts
                    stream_callback = None
                    continue
                raise

        raise last_error  # type: ignore[misc]

    def _call_impl(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        stream_callback: Optional[Callable[[str], None]] = None,
        model: Optional[str] = None,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
    ) -> str:
        """Internal implementation of AI call."""
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
                    # ★ 构建额外参数（仅在非零时传入，避免不支持的API报错）
                    extra_params: Dict[str, Any] = {}
                    if frequency_penalty > 0:
                        extra_params["frequency_penalty"] = frequency_penalty
                    if presence_penalty > 0:
                        extra_params["presence_penalty"] = presence_penalty
                    stream = self.client.chat.completions.create(
                        model=use_model,
                        messages=messages,  # type: ignore[arg-type]
                        temperature=temperature,
                        max_tokens=current_max_tokens,
                        stream=True,
                        **extra_params,
                    )

                    full_text = ""
                    finish_reason = None
                    chunk_count = 0
                    for chunk in stream:
                        if hasattr(chunk, "choices") and chunk.choices[0].delta.content is not None:  # type: ignore[union-attr]
                            chunk_text = chunk.choices[0].delta.content  # type: ignore[union-attr]
                            full_text += chunk_text
                            chunk_count += 1
                            stream_callback(chunk_text)
                        if hasattr(chunk, "choices") and chunk.choices[0].finish_reason:  # type: ignore[union-attr]
                            finish_reason = chunk.choices[0].finish_reason  # type: ignore[union-attr]
                    logger.info(
                        f"[AIClient] Streaming complete: {chunk_count} chunks, {len(full_text)} chars"
                    )

                    if finish_reason == "length":
                        logger.warning(
                            f"⚠️ AI response truncated by max_tokens ({current_max_tokens}). "
                            f"Output length: {len(full_text)} chars. "
                            f"Consider increasing max_tokens."
                        )
                        # ★ 截断恢复：自动续写被截断的输出
                        if get_feature("truncation_recovery"):
                            recovery = TruncationRecovery()
                            if recovery.detect_truncation(full_text, finish_reason):
                                full_text = recovery.recover(
                                    client_call=self._call_impl,
                                    system_prompt=system_prompt,
                                    original_prompt=user_prompt,
                                    partial_response=full_text,
                                    temperature=temperature,
                                    max_tokens=current_max_tokens,
                                    model=use_model,
                                )

                    return full_text.strip()
                else:
                    # ★ 构建额外参数（仅在非零时传入）
                    extra_params_sync: Dict[str, Any] = {}
                    if frequency_penalty > 0:
                        extra_params_sync["frequency_penalty"] = frequency_penalty
                    if presence_penalty > 0:
                        extra_params_sync["presence_penalty"] = presence_penalty
                    response = self.client.chat.completions.create(
                        model=use_model,
                        messages=messages,  # type: ignore[arg-type]
                        temperature=temperature,
                        max_tokens=current_max_tokens,
                        **extra_params_sync,
                    )

                    finish_reason = response.choices[0].finish_reason
                    content = response.choices[0].message.content or ""
                    if finish_reason == "length":
                        logger.warning(
                            f"⚠️ AI response truncated by max_tokens ({current_max_tokens}). "
                            f"Output length: {len(content)} chars. "
                            f"Consider increasing max_tokens."
                        )
                        # ★ 截断恢复：自动续写被截断的输出
                        if get_feature("truncation_recovery"):
                            recovery = TruncationRecovery()
                            if recovery.detect_truncation(content, finish_reason):
                                content = recovery.recover(
                                    client_call=self._call_impl,
                                    system_prompt=system_prompt,
                                    original_prompt=user_prompt,
                                    partial_response=content,
                                    temperature=temperature,
                                    max_tokens=current_max_tokens,
                                    model=use_model,
                                )

                    return content.strip()

            except openai.APIError as e:
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
                        logger.error(
                            f"All max_tokens fallback levels failed: {error_msg}"
                        )
                else:
                    # 非 max_tokens 错误，直接抛出
                    raise
            except Exception as e:
                # Unexpected errors - log with stack trace
                logger.exception(f"Unexpected error in AI call: {e}")
                raise

        # 所有尝试都失败，抛出最后一个错误
        raise last_error  # type: ignore[misc]

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

            except openai.APIError as e:
                last_error = str(e)
                logger.warning(
                    f"AI call attempt {attempt + 1}/{retry_count} failed: {e}"
                )
                if attempt == retry_count - 1:
                    raise ValueError(
                        f"AI call failed after {retry_count} attempts: {e}"
                    )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"AI call attempt {attempt + 1}/{retry_count} failed (unexpected): {e}"
                )
                if attempt == retry_count - 1:
                    raise ValueError(
                        f"AI call failed after {retry_count} attempts: {e}"
                    )

        raise ValueError("AI call failed after all retries")
