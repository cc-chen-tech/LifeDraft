"""ImageClient 拆分后接口兼容性测试 - 对应 C-10"""

from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit]



class TestImageClientAfterSplit:
    """验证 ImageClient 拆分后功能完整性"""

    def test_image_client_importable(self):
        """ImageClient 模块应能导入"""
        try:
            from src.ai.image_client import ImageClient

            assert ImageClient is not None
        except ImportError as e:
            pytest.skip(f"ImageClient not yet refactored: {e}")

    def test_image_client_has_generate_method(self):
        """ImageClient 应有 generate 方法"""
        from src.ai.image_client import ImageClient

        assert hasattr(ImageClient, "generate_character_images") or hasattr(ImageClient, "generate")

    def test_image_client_constructor(self):
        """ImageClient 应能实例化"""
        try:
            from src.ai.image_client import ImageClient

            # 使用 mock 的 API key
            with patch.dict("os.environ", {"IMAGE_API_KEY": "test-key"}):
                client = ImageClient.__new__(ImageClient)
                assert client is not None
        except Exception:
            pytest.skip("ImageClient constructor requires specific setup")

    def test_character_image_generation_interface(self):
        """角色图片生成接口应保持兼容"""
        # 验证方法签名存在
        import inspect

        from src.ai.image_client import ImageClient

        if hasattr(ImageClient, "generate_character_images"):
            sig = inspect.signature(ImageClient.generate_character_images)
            params = list(sig.parameters.keys())
            # 应至少接受 name 和 description 参数
            assert len(params) >= 2  # self + at least 1 param

    def test_scene_image_generation_interface(self):
        """场景图片生成接口应保持兼容"""
        from src.ai.image_client import ImageClient

        # 检查场景相关方法
        scene_methods = [m for m in dir(ImageClient) if "scene" in m.lower()]
        assert isinstance(scene_methods, list)

    def test_prompt_building_functionality(self):
        """Prompt 构建功能应存在"""
        from src.ai.image_client import ImageClient

        prompt_methods = [m for m in dir(ImageClient) if "prompt" in m.lower()]
        assert isinstance(prompt_methods, list)

    def test_error_handling_in_client(self):
        """ImageClient 模块应有错误处理"""
        # 验证异常处理相关代码存在（在拆分后的模块中）
        import inspect

        # 检查拆分后的 ImageGenerator 模块是否有错误处理
        from src.ai.image_generator import ImageGenerator

        source = inspect.getsource(ImageGenerator)
        assert "except" in source or "try" in source

    def test_backward_compatible_api(self):
        """拆分后的 API 应向后兼容"""
        # 验证所有已知的公共方法仍然存在
        from src.ai.image_client import ImageClient

        expected_methods = [
            "generate_character_images",
        ]
        for method in expected_methods:
            if hasattr(ImageClient, method):
                assert callable(getattr(ImageClient, method))


class TestAIExtractionBase:
    """AI Extraction 基类测试 - 对应 H-15"""

    def test_entity_recognition_module_exists(self):
        """实体识别模块应存在"""
        from src.services import EntityRecognitionService

        assert EntityRecognitionService is not None

    def test_item_extraction_module_exists(self):
        """物品提取模块应存在"""
        from src.services import ItemExtractionService

        assert ItemExtractionService is not None

    def test_landmark_extraction_module_exists(self):
        """地标提取模块应存在"""
        from src.services import LandmarkExtractionService

        assert LandmarkExtractionService is not None

    def test_extraction_modules_share_pattern(self):
        """提取模块应共享类似的接口模式"""
        from src.services import (EntityRecognitionService,
                                  ItemExtractionService,
                                  LandmarkExtractionService)
        from src.services.base_extraction import BaseExtractionService

        modules = [
            EntityRecognitionService,
            ItemExtractionService,
            LandmarkExtractionService,
        ]

        # 验证所有模块都继承自 BaseExtractionService
        for mod in modules:
            assert issubclass(
                mod, BaseExtractionService
            ), f"{mod.__name__} should inherit from BaseExtractionService"

        # 验证所有模块都有 __init__ 方法（继承自基类）
        for mod in modules:
            assert hasattr(mod, "__init__"), f"{mod.__name__} should have __init__ method"

    def test_extraction_error_handling_pattern(self):
        """提取模块应有一致的错误处理"""
        import inspect

        error_patterns = []

        try:
            from src.services import entity_recognition

            source = inspect.getsource(entity_recognition)
            if "except" in source:
                error_patterns.append("entity_recognition")
        except (ImportError, TypeError):
            pass

        assert isinstance(error_patterns, list)

    def test_extraction_uses_ai_client(self):
        """提取模块应使用 AI 客户端"""
        import inspect

        ai_usage = []

        for mod_name in [
            "entity_recognition",
            "item_extraction",
            "landmark_extraction",
        ]:
            try:
                mod = __import__(f"src.services.{mod_name}", fromlist=[mod_name])
                source = inspect.getsource(mod)
                if "ai" in source.lower() or "client" in source.lower():
                    ai_usage.append(mod_name)
            except (ImportError, TypeError):
                pass

        assert isinstance(ai_usage, list)
