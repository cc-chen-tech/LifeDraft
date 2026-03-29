"""AI call retry handler with error feedback injection.

Provides a unified retry mechanism for AI calls with:
- Progressive temperature decay
- Error feedback injection on retries
- Configurable retry count
"""

import logging
from typing import Any, Callable, Generic, Optional, TypeVar

from src.ai.client import AIClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AIRetryHandler:
    """Handles retry logic for AI calls with error feedback."""

    # Default temperature settings
    DEFAULT_BASE_TEMPERATURE = 0.85
    DEFAULT_MIN_TEMPERATURE = 0.5
    DEFAULT_TEMPERATURE_DECAY = 0.15

    def __init__(
        self,
        client: AIClient,
        base_temperature: float = DEFAULT_BASE_TEMPERATURE,
        min_temperature: float = DEFAULT_MIN_TEMPERATURE,
        temperature_decay: float = DEFAULT_TEMPERATURE_DECAY,
    ):
        """
        Initialize the retry handler.

        Args:
            client: AIClient instance for making AI calls
            base_temperature: Starting temperature for first attempt
            min_temperature: Minimum temperature (won't go below this)
            temperature_decay: How much to reduce temperature on each retry
        """
        self.client = client
        self.base_temperature = base_temperature
        self.min_temperature = min_temperature
        self.temperature_decay = temperature_decay

    def call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        retry_count: int = 3,
        max_tokens: int = 2000,
        stream_callback: Optional[Callable[[str], None]] = None,
        validate_func: Optional[Callable[[str], T]] = None,
        language: str = "zh",
        model: Optional[str] = None,
    ) -> str:
        """
        Make an AI call with retry logic.

        Args:
            system_prompt: System prompt text
            user_prompt: User prompt text
            retry_count: Number of retries on failure
            max_tokens: Maximum tokens to generate
            stream_callback: Optional streaming callback (only used on first attempt)
            validate_func: Optional function to validate/parse the response
            language: Language code for error messages
            model: Optional model override

        Returns:
            Raw response text from AI

        Raises:
            ValueError: If all retries fail
        """
        last_error: Optional[str] = None

        for attempt in range(retry_count):
            try:
                # Calculate temperature with decay
                current_temp = max(
                    self.min_temperature,
                    self.base_temperature - (attempt * self.temperature_decay),
                )

                # Build prompt with error feedback
                prompt = user_prompt
                if attempt > 0 and last_error:
                    if language == "zh":
                        prompt += f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题。】"
                    else:
                        prompt += f"\n\n[Previous attempt failed: {last_error}. Please avoid the same issue.]"

                # Only stream on first attempt
                cb = stream_callback if attempt == 0 else None

                logger.debug(
                    f"AI call attempt {attempt + 1}/{retry_count}, "
                    f"temperature={current_temp:.2f}"
                )

                content = self.client.call(
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    temperature=current_temp,
                    max_tokens=max_tokens,
                    stream_callback=cb,
                    model=model,
                )

                content = content.strip()

                # Validate if validator provided
                if validate_func:
                    validate_func(content)

                return content

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed: {e}")

        raise ValueError(
            f"AI call failed after {retry_count} attempts. Last error: {last_error}"
        )

    def call_with_json_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        retry_count: int = 3,
        max_tokens: int = 2000,
        language: str = "zh",
        model: Optional[str] = None,
    ) -> dict:
        """
        Make an AI call expecting JSON response, with retry logic.

        Args:
            system_prompt: System prompt text
            user_prompt: User prompt text
            retry_count: Number of retries on failure
            max_tokens: Maximum tokens to generate
            language: Language code for error messages
            model: Optional model override

        Returns:
            Parsed JSON dict

        Raises:
            ValueError: If all retries fail or JSON parsing fails
        """
        from src.ai.utils import extract_json

        last_error: Optional[str] = None

        for attempt in range(retry_count):
            try:
                current_temp = max(
                    self.min_temperature,
                    self.base_temperature - (attempt * self.temperature_decay),
                )

                prompt = user_prompt
                if attempt > 0 and last_error:
                    if language == "zh":
                        prompt += f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题，确保输出有效的JSON格式。】"
                    else:
                        prompt += f"\n\n[Previous attempt failed: {last_error}. Please ensure valid JSON output.]"

                logger.debug(
                    f"JSON AI call attempt {attempt + 1}/{retry_count}, "
                    f"temperature={current_temp:.2f}"
                )

                content = self.client.call(
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    temperature=current_temp,
                    max_tokens=max_tokens,
                    model=model,
                )

                content = content.strip()

                # Try to parse as JSON
                data = extract_json(content)
                if data:
                    return data

                last_error = "Invalid JSON format"

            except Exception as e:
                last_error = str(e)
                logger.warning(f"JSON attempt {attempt + 1} failed: {e}")

        raise ValueError(
            f"JSON AI call failed after {retry_count} attempts. Last error: {last_error}"
        )


def create_retry_handler(
    client: AIClient,
    temperature_preset: str = "balanced",
) -> AIRetryHandler:
    """
    Create a retry handler with preset temperature settings.

    Args:
        client: AIClient instance
        temperature_preset: One of 'creative', 'balanced', 'conservative'

    Returns:
        Configured AIRetryHandler
    """
    presets = {
        "creative": {
            "base_temperature": 0.95,
            "min_temperature": 0.7,
            "temperature_decay": 0.1,
        },
        "balanced": {
            "base_temperature": 0.85,
            "min_temperature": 0.5,
            "temperature_decay": 0.15,
        },
        "conservative": {
            "base_temperature": 0.7,
            "min_temperature": 0.4,
            "temperature_decay": 0.1,
        },
    }

    settings = presets.get(temperature_preset, presets["balanced"])

    return AIRetryHandler(client=client, **settings)
