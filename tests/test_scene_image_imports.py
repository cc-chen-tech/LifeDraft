"""SceneImage module imports test.

验证 scene_service 和 models 的导入路径正确。
"""

import ast
import threading
from pathlib import Path


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

    def test_images_router_does_not_call_missing_round_illustration_methods(self):
        """图片路由后台生成路径不应调用不存在的 RoundIllustrationService 方法。"""
        from src.game.round.illustration_service import RoundIllustrationService

        router_path = Path(__file__).resolve().parents[1] / "src/api/routers/images.py"
        tree = ast.parse(router_path.read_text(encoding="utf-8"))
        called_methods: set[str] = set()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "illustration_service"
            ):
                called_methods.add(func.attr)

        missing_methods = sorted(
            method
            for method in called_methods
            if method.startswith("generate") and not hasattr(RoundIllustrationService, method)
        )
        assert missing_methods == []

    def test_background_scene_generation_uses_standard_image_service(self, monkeypatch):
        """后台场景插画触发器应复用 ImageService 的标准场景图生成路径。"""
        from src.api.routers import images
        from src.database import models

        calls: list[dict[str, object]] = []

        class InlineThread:
            def __init__(self, target, name=None, daemon=None):
                self.target = target
                self.name = name
                self.daemon = daemon

            def start(self):
                self.target()

        class FakeDB:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        class FakeImageService:
            def __init__(self, db):
                self.db = db

            def generate_round_scene_image(self, **kwargs):
                calls.append(kwargs)
                return type("Scene", (), {"scene_id": 42})()

        monkeypatch.setattr(threading, "Thread", InlineThread)
        monkeypatch.setattr(models, "SessionLocal", lambda: FakeDB())
        monkeypatch.setattr(images, "ImageService", FakeImageService)

        images._trigger_scene_generation_in_background(
            game_id=1,
            week=0,
            round_number=2,
            stage="event",
            story_text="林见微在码头发现账册。",
            character_settings={"identity": {"name": "林见微"}},
            player_name="林见微",
        )

        assert calls == [
            {
                "game_id": 1,
                "round_number": 2,
                "story_text": "林见微在码头发现账册。",
                "character_settings": {"identity": {"name": "林见微"}},
                "player_name": "林见微",
                "stage": "event",
                "week": 0,
            }
        ]

    def test_background_scene_generation_deduplicates_in_flight_key(self, monkeypatch):
        """同一 game/week/round/stage 正在生成时，不应重复启动后台线程。"""
        from src.api.routers import images

        started_threads: list[str | None] = []

        class HoldingThread:
            def __init__(self, target, name=None, daemon=None):
                self.target = target
                self.name = name
                self.daemon = daemon

            def start(self):
                started_threads.append(self.name)

        monkeypatch.setattr(threading, "Thread", HoldingThread)
        images._scene_image_inflight.clear()

        try:
            for _ in range(2):
                images._trigger_scene_generation_in_background(
                    game_id=7,
                    week=2,
                    round_number=1,
                    stage="result",
                    story_text="林见微沿着医院数据造假线索追查。",
                    character_settings={"identity": {"name": "林见微"}},
                    player_name="林见微",
                )

            assert started_threads == ["scene-gen-7-2-1-result"]
            assert images._scene_image_inflight == {"7:2:1:result"}
        finally:
            images._scene_image_inflight.clear()

    def test_background_provider_failure_is_cached_safely(self, monkeypatch):
        """供应商失败应缓存结构化字段，并释放 in-flight key。"""
        from src.ai.image_exceptions import ImageProviderError
        from src.api.routers import images
        from src.database import models
        from src.services.image_service import ImageProviderServiceError

        class InlineThread:
            def __init__(self, target, name=None, daemon=None):
                self.target = target

            def start(self):
                self.target()

        class FakeDB:
            def close(self):
                pass

        class FailingImageService:
            def __init__(self, db):
                self.db = db

            def generate_round_scene_image(self, **kwargs):
                raise ImageProviderServiceError.from_provider(
                    ImageProviderError(
                        code="minimax_2056",
                        category="capacity",
                        retryable=False,
                        public_message="图片生成额度暂时不可用，请稍后再试",
                        provider_trace_id="trace-safe-1",
                    )
                )

        monkeypatch.setattr(threading, "Thread", InlineThread)
        monkeypatch.setattr(models, "SessionLocal", lambda: FakeDB())
        monkeypatch.setattr(images, "ImageService", FailingImageService)
        images._scene_image_inflight.clear()
        key = images._get_event_key(7, 2, 1, "event")
        images._scene_image_latest.pop(key, None)

        try:
            images._trigger_scene_generation_in_background(
                game_id=7,
                week=2,
                round_number=1,
                stage="event",
                story_text="林见微沿着线索追查。",
                character_settings={"identity": {"name": "林见微"}},
                player_name="林见微",
            )

            assert images._scene_image_latest[key] == {
                "type": "scene_image_failed",
                "game_id": 7,
                "round_number": 1,
                "week": 2,
                "stage": "event",
                "code": "minimax_2056",
                "message": "图片生成额度暂时不可用，请稍后再试",
                "retryable": False,
                "provider_trace_id": "trace-safe-1",
                "timestamp": images._scene_image_latest[key]["timestamp"],
            }
            assert key not in images._scene_image_inflight
        finally:
            images._scene_image_latest.pop(key, None)
            images._scene_image_inflight.clear()
