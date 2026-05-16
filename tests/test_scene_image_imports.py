"""SceneImage module imports test.

验证 scene_service 和 models 的导入路径正确。
"""


class TestSceneImageImports:
    """SceneImage 导入验证测试。"""

    def test_models_scene_image_importable(self):
        """SceneImage 模型应可从 database.models 导入。"""
        from src.database.models import SceneImage

        assert SceneImage is not None
        assert SceneImage.__tablename__ == "scene_images"

    def test_scene_service_importable(self):
        """SceneImageService 应可从 services.image.scene_service 导入。"""
        from src.services.image.scene_service import SceneImageService

        assert SceneImageService is not None

    def test_scene_service_has_generate_method(self):
        """SceneImageService 应有 generate_round_scene_image 方法。"""
        from src.services.image.scene_service import SceneImageService

        assert hasattr(SceneImageService, "generate_round_scene_image")
        assert callable(getattr(SceneImageService, "generate_round_scene_image"))

    def test_integrity_error_importable(self):
        """sqlalchemy.exc.IntegrityError 应可导入（服务代码使用）。"""
        from sqlalchemy.exc import IntegrityError

        assert IntegrityError is not None
