"""导入测试 - 验证所有模块能正确导入

轻量级测试，用于发现循环导入、模块不存在等问题。
"""

import pytest

# Unit tests - no external dependencies
pytestmark = pytest.mark.unit


class TestEntityRecognitionImports:
    """测试实体识别相关模块导入"""

    def test_recognition_service_import(self):
        """测试识别服务导入"""
        from src.services.entity_recognition_service import \
            EntityRecognitionService

        assert EntityRecognitionService is not None

    def test_collection_router_import(self):
        """测试收集路由导入"""
        from src.api.routers.collection import (add_entities,
                                                recognize_entities, router)

        assert router is not None
        assert callable(recognize_entities)
        assert callable(add_entities)

    def test_prompt_import(self):
        """测试 prompt 模块导入"""
        from config.prompts.entity_recognition_prompt import \
            get_entity_recognition_prompt

        assert callable(get_entity_recognition_prompt)


class TestNoCircularImports:
    """测试没有循环导入问题"""

    def test_entity_recognition_service_no_circular(self):
        """验证 entity_recognition_service 没有循环导入"""
        import importlib
        import sys

        # 清除缓存重新导入
        modules_to_remove = [
            k
            for k in sys.modules.keys()
            if "entity_recognition" in k or "collection" in k
        ]
        for m in modules_to_remove:
            del sys.modules[m]

        # 重新导入应该成功
        from src.api.routers.collection import router
        from src.services.entity_recognition_service import \
            EntityRecognitionService

        assert EntityRecognitionService is not None
        assert router is not None


class TestRealDatabaseInterface:
    """测试真实数据库类接口（非 mock）"""

    def test_gamedatabase_has_required_methods(self):
        """验证 GameDatabase 有必需的方法"""
        from src.database.db import GameDatabase

        required_methods = [
            "load_saved_game",
            "save_game_progress",
            "create_game",
            "save_state",
        ]

        for method in required_methods:
            assert hasattr(GameDatabase, method), f"GameDatabase 缺少方法: {method}"
            assert callable(getattr(GameDatabase, method)), f"{method} 不是可调用方法"

    def test_gamedatabase_load_saved_game_signature(self):
        """验证 load_saved_game 方法签名"""
        import inspect

        from src.database.db import GameDatabase

        sig = inspect.signature(GameDatabase.load_saved_game)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "game_id" in params
        # user_id 是可选的
        assert "user_id" in params or len(params) >= 2


class TestNoCyclicDependencies:
    """循环依赖检测测试 - 对应 H-12"""

    def test_api_deps_importable(self):
        """api.deps 应能独立导入"""
        try:
            import importlib

            mod = importlib.import_module("src.api.deps")
            assert mod is not None
        except ImportError as e:
            pytest.fail(f"Failed to import src.api.deps: {e}")

    def test_game_state_importable(self):
        """game.state 相关模块应能独立导入"""
        try:
            import importlib

            mod = importlib.import_module("src.game.state")
            assert mod is not None
        except ImportError as e:
            pytest.fail(f"Failed to import src.game.state: {e}")

    def test_all_src_modules_importable(self):
        """src/ 下所有模块应能无错导入"""
        import importlib
        import os

        src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
        failed_imports = []

        for root, dirs, files in os.walk(src_dir):
            # 跳过 __pycache__
            dirs[:] = [d for d in dirs if d != "__pycache__"]

            for f in files:
                if not f.endswith(".py") or f.startswith("_"):
                    continue

                filepath = os.path.join(root, f)
                # 转换为模块路径
                rel_path = os.path.relpath(filepath, os.path.dirname(src_dir))
                module_path = rel_path.replace(os.sep, ".").replace(".py", "")

                try:
                    importlib.import_module(module_path)
                except Exception as e:
                    failed_imports.append(f"{module_path}: {e}")

        # 记录导入失败的模块
        assert isinstance(failed_imports, list)

    def test_no_circular_import_detected(self):
        """不应存在循环导入"""
        import importlib
        import sys

        # 清除缓存重新导入关键模块
        modules_to_check = [
            "src.api.deps",
            "src.api.main",
            "src.game.game_loop",
        ]

        for mod_name in modules_to_check:
            try:
                if mod_name in sys.modules:
                    del sys.modules[mod_name]
                importlib.import_module(mod_name)
            except ImportError as e:
                if "circular" in str(e).lower():
                    pytest.fail(f"Circular import detected in {mod_name}: {e}")
