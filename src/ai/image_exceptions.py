"""Image generation exceptions.

定义图像生成相关的所有异常类。
"""

from typing import Optional


class ImageGenerationError(Exception):
    """图像生成基础错误"""

    pass


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
