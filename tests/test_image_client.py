"""Tests for ImageClient - 图像生成客户端测试"""

import base64
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.ai.image_client import (
    ContentInspectionError,
    ImageClient,
    ImageGenerationError,
)


class MockSettings:
    """Mock settings for testing"""

    IMAGE_API_KEY = "test-api-key"
    IMAGE_API_BASE_URL = "https://api.example.com/v1"
    IMAGE_MODEL = "test-model"
    IMAGE_GENERATION_TIMEOUT = 30
    IMAGE_MAX_RETRIES = 3
    TEXT_TO_IMAGE_MODELS = "model1,model2"
    IMAGE_EDIT_MODELS = "edit-model1"
    SCENE_ANALYZER_API_KEY = None
    SCENE_ANALYZER_BASE_URL = None
    SCENE_ANALYZER_MODEL = "deepseek-chat"
    OPENAI_API_KEY = None
    OPENAI_BASE_URL = None

    def get_image_api_key(self):
        return self.IMAGE_API_KEY

    def get_image_api_base_url(self):
        return self.IMAGE_API_BASE_URL


class TestImageClientInit:
    """初始化测试"""

    @patch("src.ai.image_client.settings")
    def test_init_with_defaults(self, mock_settings):
        """测试默认初始化"""
        mock_settings.get_image_api_key.return_value = "test-key"
        mock_settings.get_image_api_base_url.return_value = "https://api.test.com"
        mock_settings.IMAGE_MODEL = "test-model"
        mock_settings.IMAGE_GENERATION_TIMEOUT = 30
        mock_settings.IMAGE_MAX_RETRIES = 3
        mock_settings.TEXT_TO_IMAGE_MODELS = "model1,model2"
        mock_settings.IMAGE_EDIT_MODELS = "edit-model"

        client = ImageClient()

        assert client.api_key == "test-key"
        assert client.base_url == "https://api.test.com"
        assert client.model == "test-model"

    @patch("src.ai.image_client.settings")
    def test_init_with_custom_params(self, mock_settings):
        """测试自定义参数初始化"""
        mock_settings.IMAGE_GENERATION_TIMEOUT = 30
        mock_settings.IMAGE_MAX_RETRIES = 3
        mock_settings.TEXT_TO_IMAGE_MODELS = "model1"
        mock_settings.IMAGE_EDIT_MODELS = "edit-model"

        client = ImageClient(
            api_key="custom-key",
            base_url="https://custom.api.com",
            model="custom-model",
        )

        assert client.api_key == "custom-key"
        assert client.base_url == "https://custom.api.com"
        assert client.model == "custom-model"

    @patch("src.ai.image_client.settings")
    def test_init_raises_without_api_key(self, mock_settings):
        """测试无API密钥时抛出异常"""
        mock_settings.get_image_api_key.return_value = None
        mock_settings.get_image_api_base_url.return_value = "https://api.test.com"
        mock_settings.TEXT_TO_IMAGE_MODELS = ""
        mock_settings.IMAGE_EDIT_MODELS = ""

        with pytest.raises(ValueError) as exc_info:
            ImageClient()

        assert "API key" in str(exc_info.value)

    @patch("src.ai.image_client.settings")
    def test_init_raises_without_base_url(self, mock_settings):
        """测试无Base URL时抛出异常"""
        mock_settings.get_image_api_key.return_value = "test-key"
        mock_settings.get_image_api_base_url.return_value = None
        mock_settings.TEXT_TO_IMAGE_MODELS = ""
        mock_settings.IMAGE_EDIT_MODELS = ""

        with pytest.raises(ValueError) as exc_info:
            ImageClient()

        assert "base URL" in str(exc_info.value)


class TestImageGenerationError:
    """错误类测试"""

    def test_image_generation_error(self):
        """测试图像生成错误"""
        error = ImageGenerationError("生成失败")
        assert str(error) == "生成失败"

    def test_content_inspection_error(self):
        """测试内容审核错误"""
        error = ContentInspectionError("内容审核失败", original_prompt="不合适的提示词")
        assert str(error) == "内容审核失败"
        assert error.original_prompt == "不合适的提示词"

    def test_content_inspection_error_inheritance(self):
        """测试内容审核错误继承"""
        error = ContentInspectionError("测试")
        assert isinstance(error, ImageGenerationError)


class TestBuildFallbackPrompt:
    """测试Fallback Prompt构建"""

    @patch("src.ai.image_client.settings")
    def test_build_fallback_prompt_basic(self, mock_settings):
        """测试基本Fallback Prompt构建"""
        mock_settings.get_image_api_key.return_value = "test-key"
        mock_settings.get_image_api_base_url.return_value = "https://api.test.com"
        mock_settings.IMAGE_MODEL = "test-model"
        mock_settings.IMAGE_GENERATION_TIMEOUT = 30
        mock_settings.IMAGE_MAX_RETRIES = 3
        mock_settings.TEXT_TO_IMAGE_MODELS = "model1"
        mock_settings.IMAGE_EDIT_MODELS = "edit-model"

        client = ImageClient()

        character_info = {
            "name": "张三",
            "age": 25,
            "gender": "男",
            "appearance": "高大帅气",
        }

        prompt = client._build_fallback_prompt(character_info)

        assert "张三" in prompt
        assert "25" in prompt or "男" in prompt


class TestImageClientMethods:
    """测试客户端方法"""

    @patch("src.ai.image_client.settings")
    def test_generate_image_prompt_with_deepseek_no_key(self, mock_settings):
        """测试无DeepSeek密钥时使用Fallback"""
        mock_settings.get_image_api_key.return_value = "test-key"
        mock_settings.get_image_api_base_url.return_value = "https://api.test.com"
        mock_settings.IMAGE_MODEL = "test-model"
        mock_settings.IMAGE_GENERATION_TIMEOUT = 30
        mock_settings.IMAGE_MAX_RETRIES = 3
        mock_settings.TEXT_TO_IMAGE_MODELS = "model1"
        mock_settings.IMAGE_EDIT_MODELS = "edit-model"
        mock_settings.SCENE_ANALYZER_API_KEY = None
        mock_settings.OPENAI_API_KEY = None

        client = ImageClient()

        character_info = {"name": "测试角色"}
        prompt = client.generate_image_prompt_with_deepseek(character_info)

        # 应该返回 fallback prompt
        assert prompt is not None


class TestModelLists:
    """测试模型列表解析"""

    @patch("src.ai.image_client.settings")
    def test_model_lists_parsed(self, mock_settings):
        """测试模型列表正确解析"""
        mock_settings.get_image_api_key.return_value = "test-key"
        mock_settings.get_image_api_base_url.return_value = "https://api.test.com"
        mock_settings.IMAGE_MODEL = "test-model"
        mock_settings.IMAGE_GENERATION_TIMEOUT = 30
        mock_settings.IMAGE_MAX_RETRIES = 3
        mock_settings.TEXT_TO_IMAGE_MODELS = "model1, model2, model3"
        mock_settings.IMAGE_EDIT_MODELS = "edit1, edit2"

        client = ImageClient()

        assert len(client.text_to_image_models) == 3
        assert len(client.image_edit_models) == 2

    @patch("src.ai.image_client.settings")
    def test_empty_model_lists(self, mock_settings):
        """测试空模型列表"""
        mock_settings.get_image_api_key.return_value = "test-key"
        mock_settings.get_image_api_base_url.return_value = "https://api.test.com"
        mock_settings.IMAGE_MODEL = "test-model"
        mock_settings.IMAGE_GENERATION_TIMEOUT = 30
        mock_settings.IMAGE_MAX_RETRIES = 3
        mock_settings.TEXT_TO_IMAGE_MODELS = ""
        mock_settings.IMAGE_EDIT_MODELS = ""

        client = ImageClient()

        assert client.text_to_image_models == []
        assert client.image_edit_models == []
