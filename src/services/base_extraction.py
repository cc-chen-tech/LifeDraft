"""AI 提取服务基类。

提供统一的 AI 调用、JSON 解析、故事截断等公共功能。
被 EntityRecognitionService、ItemExtractionService、LandmarkExtractionService 继承。
"""

import logging
from typing import Any, Dict, Optional

from src.ai.system_prompts import get_system_prompt
from src.ai.utils import extract_json

logger = logging.getLogger(__name__)


class BaseExtractionService:
    """AI 提取服务基类。

    提供通用的 AI 调用和响应解析功能。
    """

    def __init__(self, ai_client):
        """
        Args:
            ai_client: AIClient 实例
        """
        self.ai_client = ai_client

    def _call_ai(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """统一的 AI 调用逻辑。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            AI 响应文本
        """
        return self.ai_client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _get_system_prompt(self, prompt_type: str, language: str) -> str:
        """获取系统提示词。

        Args:
            prompt_type: 提示词类型（如 "story_analyzer"）
            language: 语言代码

        Returns:
            系统提示词
        """
        return get_system_prompt(prompt_type, language)

    def _parse_json_response(
        self,
        response: str,
        expected_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """统一的 JSON 解析逻辑。

        Args:
            response: AI 响应文本
            expected_key: 期望的顶层键（可选）

        Returns:
            解析后的字典，失败返回 None
        """
        try:
            data = extract_json(response)
            if not data:
                logger.warning("Could not parse response as JSON")
                return None

            if expected_key and expected_key not in data:
                logger.warning(f"Expected key '{expected_key}' not found in response")
                return None

            return data
        except Exception as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None

    def _truncate_story(
        self,
        story_text: str,
        max_length: int = 15000,
        truncation_message: str = "\n...[故事过长，已截断]",
    ) -> str:
        """统一的故事截断逻辑。

        Args:
            story_text: 原始故事文本
            max_length: 最大长度
            truncation_message: 截断提示信息

        Returns:
            截断后的文本
        """
        if len(story_text) <= max_length:
            return story_text

        logger.warning(
            f"Story text too long ({len(story_text)} chars), truncating to {max_length}"
        )
        return story_text[:max_length] + truncation_message

    def _validate_importance(self, importance: str) -> str:
        """验证重要程度。

        Args:
            importance: 重要程度值

        Returns:
            有效的重要程度值
        """
        valid_values = ("critical", "important", "normal")
        if importance not in valid_values:
            return "normal"
        return importance

    def _validate_category(
        self,
        category: str,
        valid_categories: tuple,
        default: str = "other",
    ) -> str:
        """验证类别。

        Args:
            category: 类别值
            valid_categories: 有效类别元组
            default: 默认值

        Returns:
            有效的类别值
        """
        if category not in valid_categories:
            return default
        return category
