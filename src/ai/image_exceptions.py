"""Image generation exceptions.

定义图像生成相关的所有异常类。
"""

from typing import Literal, Optional


class ImageGenerationError(Exception):
    """图像生成基础错误"""


ImageProviderCategory = Literal[
    "configuration",
    "authentication",
    "capacity",
    "rate_limit",
    "timeout",
    "upstream",
    "invalid_request",
    "invalid_response",
]


class ImageProviderError(ImageGenerationError):
    """Safe, typed failure reported by the configured image provider."""

    def __init__(
        self,
        *,
        code: str,
        category: ImageProviderCategory,
        retryable: bool,
        public_message: str,
        provider_trace_id: Optional[str] = None,
    ) -> None:
        super().__init__(public_message)
        self.code = code
        self.category = category
        self.retryable = retryable
        self.public_message = public_message
        self.provider_trace_id = provider_trace_id


class ContentInspectionError(ImageGenerationError):
    """内容审核错误 - 触发了平台的内容安全检测"""

    def __init__(
        self,
        message: str,
        original_prompt: Optional[str] = None,
        api_error_message: Optional[str] = None,
    ):
        super().__init__(message)
        self.original_prompt = original_prompt
        self.api_error_message = api_error_message  # 阿里云返回的原始错误信息
