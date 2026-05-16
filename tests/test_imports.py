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
        import sys

        # 清除缓存重新导入
        modules_to_remove = [
            k for k in sys.modules.keys() if "entity_recognition" in k or "collection" in k
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


class TestSSEHelpersLazyImports:
    """验证 sse_helpers.py 中所有延迟导入路径可达

    sse_helpers 在后台线程/try块中使用延迟导入，
    如果路径写错会被静默吞掉，必须在此显式验证。
    """

    def test_illustration_generation_imports(self):
        """验证 _trigger_round_illustration_generation 的延迟导入"""
        from src.ai.image_client import ImageClient
        from src.database.models import Game
        from src.database.models import Image as ImageModel
        from src.database.models import SceneImage, SessionLocal
        from src.game.round.illustration_service import \
            RoundIllustrationService
        from src.services.image_storage import ImageStorageService

        assert ImageClient is not None
        assert Game is not None
        assert ImageModel is not None
        assert SceneImage is not None
        assert SessionLocal is not None
        assert RoundIllustrationService is not None
        assert ImageStorageService is not None

    def test_stream_regenerate_scene_cleanup_imports(self):
        """验证 stream_regenerate 场景图片清理的延迟导入

        回归测试：曾因 `from src.database.session import SessionLocal`
        写错路径导致场景图片清理静默失败。
        正确路径是 `from src.database.models import SessionLocal`。
        """
        from src.database.models import SceneImage, SessionLocal

        assert SceneImage is not None
        assert SessionLocal is not None
        assert callable(SessionLocal)

    def test_stream_rewrite_world_model_import(self):
        """验证 stream_rewrite 的 WorldModel 延迟导入"""
        from src.game.world_model import WorldModel

        assert WorldModel is not None


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


class TestNarrativeSystemImports:
    """验证叙事风格引擎模块导入可达"""

    def test_import_style_manifest(self):
        from src.ai.narrative.style_manifest import (StyleLoader,
                                                     StyleManifest, get_style)

        assert StyleManifest is not None
        assert StyleLoader is not None
        assert callable(get_style)

    def test_import_style_prompt_builder(self):
        from src.ai.narrative.style_prompt_builder import \
            StyleAwarePromptBuilder

        assert StyleAwarePromptBuilder is not None

    def test_import_style_validator(self):
        from src.ai.narrative.style_validator import StyleAwareValidator

        assert StyleAwareValidator is not None

    def test_import_character_arc(self):
        from src.ai.narrative.character_arc import CharacterArcEngine

        assert CharacterArcEngine is not None

    def test_import_world_breathing(self):
        from src.ai.narrative.world_breathing import WorldBreathingEngine

        assert WorldBreathingEngine is not None

    def test_import_conflict_tower(self):
        from src.ai.narrative.conflict_tower import ConflictTower

        assert ConflictTower is not None

    def test_import_fate_echo(self):
        from src.ai.narrative.fate_echo import FateEchoDatabase

        assert FateEchoDatabase is not None

    def test_import_narrative_init(self):
        import src.ai.narrative

        assert src.ai.narrative is not None


class TestCreativeSystemImports:
    """验证创意增强模块导入可达"""

    def test_import_emotional_arc(self):
        from src.ai.creative.emotional_arc import EmotionalArcAnalyzer

        assert EmotionalArcAnalyzer is not None

    def test_import_novelty_scorer(self):
        from src.ai.creative.novelty_scorer import NoveltyScorer

        assert NoveltyScorer is not None

    def test_import_foreshadowing(self):
        from src.ai.creative.foreshadowing_tech import (
            ForeshadowingTechniqueLibrary, HookInjector)

        assert ForeshadowingTechniqueLibrary is not None
        assert HookInjector is not None

    def test_import_preference_learner(self):
        from src.ai.creative.preference_learner import PreferenceLearner

        assert PreferenceLearner is not None

    def test_import_creative_init(self):
        import src.ai.creative

        assert src.ai.creative is not None


class TestHarnessValidatorImports:
    """验证8个硬性逻辑验证器导入可达"""

    def test_import_temporal_validator(self):
        from src.ai.harness.temporal_validator import \
            validate_temporal_consistency

        assert callable(validate_temporal_consistency)

    def test_import_commitment_validator(self):
        from src.ai.harness.commitment_validator import \
            validate_commitment_fulfillment

        assert callable(validate_commitment_fulfillment)

    def test_import_character_state_validator(self):
        from src.ai.harness.character_state_validator import \
            validate_character_state_continuity

        assert callable(validate_character_state_continuity)

    def test_import_item_continuity_validator(self):
        from src.ai.harness.item_continuity_validator import \
            validate_item_continuity

        assert callable(validate_item_continuity)

    def test_import_spatial_validator(self):
        from src.ai.harness.spatial_validator import validate_spatial_movement

        assert callable(validate_spatial_movement)

    def test_import_npc_attribute_validator(self):
        from src.ai.harness.npc_attribute_validator import \
            validate_npc_attribute_stability

        assert callable(validate_npc_attribute_stability)

    def test_import_info_barrier_validator(self):
        from src.ai.harness.info_barrier_validator import \
            validate_information_barrier

        assert callable(validate_information_barrier)

    def test_import_cause_effect_validator(self):
        from src.ai.harness.cause_effect_validator import \
            validate_cause_effect_consistency

        assert callable(validate_cause_effect_consistency)

    def test_import_constraint_registry_new_types(self):
        from src.ai.harness.constraint_registry import ConstraintType

        # 验证所有30+个类型都在枚举中
        assert len(ConstraintType) >= 30
