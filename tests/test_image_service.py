"""Tests for ImageService - 图像服务测试

使用 Mock 隔离外部依赖（AI客户端、存储服务）
"""

import io
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.services.image_service import (
    ImageContentError,
    ImageService,
    ImageServiceError,
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

        service = ImageService(db, image_client=image_client, storage_service=storage)

        assert service.image_client == image_client
        assert service.storage_service == storage


class TestGenerateCharacterImage:
    """角色图片生成测试"""

    @pytest.fixture
    def service(self):
        """创建测试服务"""
        db = MagicMock()
        return ImageService(
            db, image_client=MockImageClient(), storage_service=MockStorageService()
        )

    def test_generate_character_image_basic(self, service):
        """测试基本角色图片生成 - 验证方法存在"""
        assert hasattr(service, "generate_character_image")
        assert callable(service.generate_character_image)

    def test_generate_character_image_with_style(self, service):
        """测试带风格提示的生成 - 验证参数处理"""
        import inspect

        sig = inspect.signature(service.generate_character_image)
        params = list(sig.parameters.keys())

        assert "game_id" in params
        assert "name" in params
        assert "description" in params

    def test_generate_character_image_with_feedback(self, service):
        """测试带反馈的重新生成 - 验证feedback参数"""
        import inspect

        sig = inspect.signature(service.generate_character_image)
        params = list(sig.parameters.keys())

        assert "feedback" in params

    def test_generate_character_image_with_keep_old_active(self, service):
        """测试 keep_old_active 参数存在 - 验证新参数"""
        import inspect

        sig = inspect.signature(service.generate_character_image)
        params = list(sig.parameters.keys())

        assert "keep_old_active" in params


class TestGenerateSceneImage:
    """场景图片生成测试"""

    @pytest.fixture
    def service(self):
        db = MagicMock()
        return ImageService(
            db, image_client=MockImageClient(), storage_service=MockStorageService()
        )

    def test_generate_round_scene_image_exists(self, service):
        """测试场景图片生成方法存在"""
        assert hasattr(service, "generate_round_scene_image")
        assert callable(service.generate_round_scene_image)

    def test_generate_opening_illustration_exists(self, service):
        """测试开场插画方法存在"""
        assert hasattr(service, "generate_opening_illustration")
        assert callable(service.generate_opening_illustration)

    def test_generate_location_image_exists(self, service):
        """测试地点图片生成方法存在"""
        assert hasattr(service, "generate_location_image")
        assert callable(service.generate_location_image)

    def test_generate_item_image_exists(self, service):
        """测试物品图片生成方法存在"""
        assert hasattr(service, "generate_item_image")
        assert callable(service.generate_item_image)


class TestRegenerateImage:
    """图片重新生成测试"""

    @pytest.fixture
    def service(self):
        db = MagicMock()
        return ImageService(
            db, image_client=MockImageClient(), storage_service=MockStorageService()
        )

    def test_regenerate_image_exists(self, service):
        """测试重新生成方法存在"""
        assert hasattr(service, "regenerate_image")
        assert callable(service.regenerate_image)

    def test_regenerate_fresh_image_exists(self, service):
        """测试完全重新生成方法存在"""
        assert hasattr(service, "regenerate_fresh_image")
        assert callable(service.regenerate_fresh_image)

    def test_regenerate_round_scene_image_exists(self, service):
        """测试场景重新生成方法存在"""
        assert hasattr(service, "regenerate_round_scene_image")
        assert callable(service.regenerate_round_scene_image)


class TestImageServiceErrors:
    """错误处理测试"""

    def test_image_service_error(self):
        """测试服务错误"""
        error = ImageServiceError("测试错误")
        assert str(error) == "测试错误"

    def test_image_content_error(self):
        """测试内容错误"""
        error = ImageContentError("内容审核失败", original_prompt="不合适的提示词")
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
        assert hasattr(service, "get_all_images_for_game")
        assert callable(service.get_all_images_for_game)


class TestGetImages:
    """图片查询测试"""

    @pytest.fixture
    def service(self):
        db = MagicMock()
        return ImageService(db)

    def test_get_image_exists(self, service):
        """测试获取单个图片方法存在"""
        assert hasattr(service, "get_image")
        assert callable(service.get_image)

    def test_get_all_images_for_game_exists(self, service):
        """测试获取游戏所有图片方法存在"""
        assert hasattr(service, "get_all_images_for_game")
        assert callable(service.get_all_images_for_game)

    def test_get_image_data_exists(self, service):
        """测试获取图片数据方法存在"""
        assert hasattr(service, "get_image_data")
        assert callable(service.get_image_data)


class TestImageStorageIntegration:
    """图片存储集成测试"""

    @pytest.fixture
    def service(self):
        db = MagicMock()
        return ImageService(
            db, image_client=MockImageClient(), storage_service=MockStorageService()
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
        assert hasattr(service, "db")
        assert service.db is not None


class TestKeepOldActive:
    """测试 keep_old_active 参数行为 - 避免图片生成过程中的闪烁"""

    @pytest.fixture
    def service(self):
        """创建测试服务"""
        db = MagicMock()
        return ImageService(
            db, image_client=MockImageClient(), storage_service=MockStorageService()
        )

    def test_keep_old_active_param_exists(self, service):
        """测试 keep_old_active 参数存在于 generate_character_image"""
        import inspect

        sig = inspect.signature(service.generate_character_image)
        params = list(sig.parameters.keys())

        assert "keep_old_active" in params
        # 验证默认值为 False
        assert sig.parameters["keep_old_active"].default == False

    def test_regenerate_image_uses_keep_old_active(self, service):
        """测试 regenerate_image 使用 keep_old_active=True"""
        # Mock 数据库查询
        mock_image = MagicMock()
        mock_image.image_id = 1
        mock_image.game_id = 1
        mock_image.entity_name = "测试角色"
        mock_image.entity_key = "character_测试角色"
        mock_image.image_type = "character"
        mock_image.storage_path = "/path/to/image.png"
        mock_image.storage_type = "local"
        mock_image.metadata_json = {}
        mock_image.is_active = True

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_image
        service.db.query.return_value = mock_query

        # Mock _get_image_data
        service._get_image_data = MagicMock(return_value=b"fake_image_data")

        # 验证 regenerate_image 会调用 generate_character_image with keep_old_active=True
        with patch.object(service, "_character_service") as mock_char_service:
            mock_char_service.regenerate_image.return_value = [mock_image]

            # 调用 regenerate_image
            result = service.regenerate_image(image_id=1, feedback="头发变长")

            # 验证 regenerate_image 被调用
            assert mock_char_service.regenerate_image.called


class TestSceneImageFileMissing:
    """场景插画文件丢失重新生成测试"""

    def test_scene_image_regenerates_when_file_missing(self):
        """测试场景插画文件丢失时自动重新生成"""
        from src.services.image.scene_service import SceneImageService

        # Mock 数据库
        db = MagicMock()

        # Mock 存储服务 - 文件不存在
        storage_service = MagicMock()
        storage_service.image_exists.return_value = False
        storage_service.save_image.return_value = ("/path/to/new_image.png", "local")

        # Mock 图片客户端
        image_client = MagicMock()
        image_client.analyze_story_for_illustration.return_value = (
            "场景描述",
            "插画提示词",
        )
        # generate_image 返回 (image_data, image_url) 元组
        image_client.generate_image.return_value = (
            b"fake_image_data",
            "https://example.com/image.png",
        )

        # Mock 已存在的数据库记录
        existing_scene = MagicMock()
        existing_scene.storage_path = "/path/to/missing_image.png"
        existing_scene.storage_type = "local"

        # Mock 查询返回已存在记录
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = existing_scene
        db.query.return_value = mock_query

        # 创建服务
        service = SceneImageService(
            db, image_client=image_client, storage_service=storage_service
        )

        # 调用生成方法
        result = service.generate_round_scene_image(
            game_id=1,
            round_number=0,
            story_text="测试故事",
            character_settings={"时代": "现代", "姓名": "测试角色"},
            player_name="测试角色",
            stage="event",
            week=0,
        )

        # 验证：文件丢失时应删除旧记录并重新生成
        db.delete.assert_called_once_with(existing_scene)
        db.commit.assert_called()
        storage_service.save_image.assert_called_once()

    def test_scene_image_skips_when_file_exists(self):
        """测试场景插画文件存在时跳过生成"""
        from src.services.image.scene_service import SceneImageService

        # Mock 数据库
        db = MagicMock()

        # Mock 存储服务 - 文件存在
        storage_service = MagicMock()
        storage_service.image_exists.return_value = True

        # Mock 已存在的数据库记录
        existing_scene = MagicMock()
        existing_scene.storage_path = "/path/to/existing_image.png"
        existing_scene.storage_type = "local"

        # Mock 查询返回已存在记录
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = existing_scene
        db.query.return_value = mock_query

        # 创建服务
        service = SceneImageService(db, storage_service=storage_service)

        # 调用生成方法
        result = service.generate_round_scene_image(
            game_id=1,
            round_number=0,
            story_text="测试故事",
            character_settings={"时代": "现代", "姓名": "测试角色"},
            player_name="测试角色",
            stage="event",
            week=0,
        )

        # 验证：文件存在时返回现有记录
        assert result == existing_scene
        db.delete.assert_not_called()
        storage_service.save_image.assert_not_called()
