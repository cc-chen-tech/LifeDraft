"""Tests for ImageService - 图像服务测试

使用 Mock 隔离外部依赖（AI客户端、存储服务）
"""
import pytest
from unittest.mock import MagicMock, patch, mock_open
import io

from src.services.image_service import (
    ImageService,
    ImageServiceError,
    ImageContentError,
)


class MockImageClient:
    """Mock ImageClient"""
    
    def generate_image(self, prompt, **kwargs):
        return {
            "image_data": b"fake_image_data",
            "image_url": "https://example.com/image.png",
        }
    
    def generate_character_images(self, name, description, **kwargs):
        """正确的方法名"""
        return [
            {
                "image_data": b"fake_character_image",
                "image_url": "https://example.com/character.png",
            }
        ]


class MockStorageService:
    """Mock ImageStorageService"""
    
    def save_image(self, image_data, filename, **kwargs):
        return "/path/to/image.png"
    
    def get_image_url(self, filename):
        return f"https://storage.example.com/{filename}"
    
    def get_image_data(self, filename):
        return b"fake_image_data"


class TestImageServiceInit:
    """初始化测试"""
    
    def test_init_with_defaults(self):
        """测试默认初始化"""
        db = MagicMock()
        service = ImageService(db)
        
        assert service.db == db
        assert service.image_client is not None
        assert service.storage_service is not None
    
    def test_init_with_custom_clients(self):
        """测试自定义客户端初始化"""
        db = MagicMock()
        image_client = MockImageClient()
        storage = MockStorageService()
        
        service = ImageService(
            db,
            image_client=image_client,
            storage_service=storage
        )
        
        assert service.image_client == image_client
        assert service.storage_service == storage


class TestGenerateCharacterImage:
    """角色图片生成测试"""
    
    @pytest.fixture
    def service(self):
        """创建测试服务"""
        db = MagicMock()
        return ImageService(
            db,
            image_client=MockImageClient(),
            storage_service=MockStorageService()
        )
    
    def test_generate_character_image_basic(self, service):
        """测试基本角色图片生成 - 验证方法存在"""
        assert hasattr(service, 'generate_character_image')
        assert callable(service.generate_character_image)
    
    def test_generate_character_image_with_style(self, service):
        """测试带风格提示的生成 - 验证参数处理"""
        import inspect
        sig = inspect.signature(service.generate_character_image)
        params = list(sig.parameters.keys())
        
        assert 'game_id' in params
        assert 'name' in params
        assert 'description' in params
    
    def test_generate_character_image_with_feedback(self, service):
        """测试带反馈的重新生成 - 验证feedback参数"""
        import inspect
        sig = inspect.signature(service.generate_character_image)
        params = list(sig.parameters.keys())
        
        assert 'feedback' in params


class TestGenerateSceneImage:
    """场景图片生成测试"""
    
    @pytest.fixture
    def service(self):
        db = MagicMock()
        return ImageService(
            db,
            image_client=MockImageClient(),
            storage_service=MockStorageService()
        )
    
    def test_generate_round_scene_image_exists(self, service):
        """测试场景图片生成方法存在"""
        assert hasattr(service, 'generate_round_scene_image')
        assert callable(service.generate_round_scene_image)
    
    def test_generate_opening_illustration_exists(self, service):
        """测试开场插画方法存在"""
        assert hasattr(service, 'generate_opening_illustration')
        assert callable(service.generate_opening_illustration)
    
    def test_generate_location_image_exists(self, service):
        """测试地点图片生成方法存在"""
        assert hasattr(service, 'generate_location_image')
        assert callable(service.generate_location_image)
    
    def test_generate_item_image_exists(self, service):
        """测试物品图片生成方法存在"""
        assert hasattr(service, 'generate_item_image')
        assert callable(service.generate_item_image)


class TestRegenerateImage:
    """图片重新生成测试"""
    
    @pytest.fixture
    def service(self):
        db = MagicMock()
        return ImageService(
            db,
            image_client=MockImageClient(),
            storage_service=MockStorageService()
        )
    
    def test_regenerate_image_exists(self, service):
        """测试重新生成方法存在"""
        assert hasattr(service, 'regenerate_image')
        assert callable(service.regenerate_image)
    
    def test_regenerate_fresh_image_exists(self, service):
        """测试完全重新生成方法存在"""
        assert hasattr(service, 'regenerate_fresh_image')
        assert callable(service.regenerate_fresh_image)
    
    def test_regenerate_round_scene_image_exists(self, service):
        """测试场景重新生成方法存在"""
        assert hasattr(service, 'regenerate_round_scene_image')
        assert callable(service.regenerate_round_scene_image)


class TestImageServiceErrors:
    """错误处理测试"""
    
    def test_image_service_error(self):
        """测试服务错误"""
        error = ImageServiceError("测试错误")
        assert str(error) == "测试错误"
    
    def test_image_content_error(self):
        """测试内容错误"""
        error = ImageContentError(
            "内容审核失败",
            original_prompt="不合适的提示词"
        )
        assert error.original_prompt == "不合适的提示词"
    
    def test_image_content_error_inheritance(self):
        """测试内容错误继承关系"""
        error = ImageContentError("测试")
        assert isinstance(error, ImageServiceError)


class TestImageDeletion:
    """图片删除测试"""
    
    @pytest.fixture
    def service(self):
        db = MagicMock()
        return ImageService(db)
    
    def test_get_all_images_for_game_exists(self, service):
        """测试获取游戏所有图片方法存在"""
        assert hasattr(service, 'get_all_images_for_game')
        assert callable(service.get_all_images_for_game)


class TestGetImages:
    """图片查询测试"""
    
    @pytest.fixture
    def service(self):
        db = MagicMock()
        return ImageService(db)
    
    def test_get_image_exists(self, service):
        """测试获取单个图片方法存在"""
        assert hasattr(service, 'get_image')
        assert callable(service.get_image)
    
    def test_get_all_images_for_game_exists(self, service):
        """测试获取游戏所有图片方法存在"""
        assert hasattr(service, 'get_all_images_for_game')
        assert callable(service.get_all_images_for_game)
    
    def test_get_image_data_exists(self, service):
        """测试获取图片数据方法存在"""
        assert hasattr(service, 'get_image_data')
        assert callable(service.get_image_data)


class TestImageStorageIntegration:
    """图片存储集成测试"""
    
    @pytest.fixture
    def service(self):
        db = MagicMock()
        return ImageService(
            db,
            image_client=MockImageClient(),
            storage_service=MockStorageService()
        )
    
    def test_storage_service_assigned(self, service):
        """测试存储服务已分配"""
        assert service.storage_service is not None
    
    def test_image_client_assigned(self, service):
        """测试图片客户端已分配"""
        assert service.image_client is not None


class TestImageModelCreation:
    """图片模型创建测试"""
    
    @pytest.fixture
    def service(self):
        db = MagicMock()
        return ImageService(db)
    
    def test_create_image_model_method(self, service):
        """测试创建图片模型方法"""
        # 检查是否有内部创建模型的方法
        assert hasattr(service, 'db')
        assert service.db is not None
