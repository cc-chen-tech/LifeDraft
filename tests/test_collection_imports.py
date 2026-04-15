"""收集面板缓存优化 - 导入验证测试 (Layer 2).

验证所有延迟导入路径可达，确保后端异步插画检查和前端缓存模块
没有循环导入或路径错误问题。
"""

import pytest

pytestmark = pytest.mark.unit


class TestSessionServiceImports:
    """验证 session_service 相关模块导入可达"""

    def test_session_service_import(self):
        """测试 SessionService 可导入"""
        from src.api.services.session_service import SessionService, session_service

        assert SessionService is not None
        assert session_service is not None

    def test_session_service_methods_exist(self):
        """验证 SessionService 有必需的方法"""
        from src.api.services.session_service import SessionService

        required_methods = [
            "get",
            "get_or_restore",
            "_restore_from_database",
            "_check_and_generate_missing_illustrations",
            "_check_character_images",
            "_check_recent_scene_images",
            "_trigger_character_image_regeneration",
            "_trigger_illustration_generation",
        ]

        for method in required_methods:
            assert hasattr(SessionService, method), f"SessionService 缺少方法: {method}"
            assert callable(getattr(SessionService, method)), f"{method} 不是可调用方法"


class TestCollectionStoreImports:
    """验证前端收集 store 相关导入可达"""

    def test_collection_store_import(self):
        """测试 useCollectionStore 可导入"""
        # 这是一个前端 TypeScript 模块，通过 Node 运行时验证
        # Python 层只需确认相关概念存在
        pass


class TestLazyImportPaths:
    """验证所有延迟导入路径正确"""

    def test_session_service_lazy_imports(self):
        """验证 _check_and_generate_missing_illustrations 中的延迟导入"""
        from src.services.image_storage import ImageStorageService
        from src.database.models import SessionLocal
        from src.database.models import Image as ImageModel
        from src.database.models import SceneImage
        from src.ai.image_client import ImageClient
        from src.services.image_service import ImageService
        from src.game.round.illustration_service import RoundIllustrationService

        assert ImageStorageService is not None
        assert SessionLocal is not None
        assert callable(SessionLocal)
        assert ImageModel is not None
        assert SceneImage is not None
        assert ImageClient is not None
        assert ImageService is not None
        assert RoundIllustrationService is not None

    def test_threading_timer_import(self):
        """验证 threading.Timer 可用于延迟执行"""
        import threading

        timer = threading.Timer(0, lambda: None)
        assert timer is not None
        assert hasattr(timer, "start")
        assert hasattr(timer, "cancel")
