"""真实 DB 集成测试 — edit 降级到 generate 后图片仍能保存

验证 RoundIllustrationService 在 edit_image 失败降级到 generate_image 后，
仍能正确保存图片到数据库和文件系统。

测试层: 真实 DB 集成测试 (Layer 4)
目标: 验证降级后保存→读取链路完整
可防止: edit 降级后图片丢失或数据库记录不完整
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.ai.image_exceptions import ImageGenerationError
from src.database.models import SceneImage
from src.game.round.illustration_service import RoundIllustrationService
from src.services.image_storage import ImageStorageService


@pytest.mark.integration
class TestImageEditFallbackDb:
    """DB 集成测试：edit 降级后图片保存完整性"""

    def test_fallback_generation_saves_to_db(self, db_session):
        """edit 降级到 generate 后，SceneImage 记录应正确写入数据库"""
        service = self._create_service(db_session)

        # Mock: edit_image 失败，generate_image 成功
        service.image_client.edit_image.side_effect = ImageGenerationError("timeout")
        service.image_client.generate_image.return_value = (
            b"fake_image_bytes",
            "prompt",
        )

        # 生成前数据库应无记录
        before_count = db_session.query(SceneImage).filter(SceneImage.game_id == 999).count()
        assert before_count == 0

        # 调用生成（带 reference_urls 会尝试 edit，然后降级到 generate）
        service._generate_round_illustration_sync(
            game_id=999,
            round_number=0,
            story_text="测试故事文本",
            character_settings={"era": "现代"},
            player_name="测试角色",
            existing_images=[
                {
                    "image_id": 1,
                    "image_type": "character",
                    "entity_name": "测试角色",
                    "image_url": "http://example.com/img.jpg",
                }
            ],
            stage="result",
            week=0,
        )

        # 生成后数据库应有记录
        after = db_session.query(SceneImage).filter(SceneImage.game_id == 999).first()
        assert after is not None, "降级生成后 SceneImage 记录应写入数据库"
        assert after.round_number == 0
        assert after.stage == "result"
        assert after.week == 0

    def test_fallback_generation_saves_file(self, db_session):
        """edit 降级到 generate 后，图片文件应保存到存储"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ImageStorageService(local_path=Path(tmpdir))
            service = self._create_service(db_session, storage)

            service.image_client.edit_image.side_effect = ImageGenerationError("timeout")
            service.image_client.generate_image.return_value = (
                b"fake_image_bytes",
                "prompt",
            )

            service._generate_round_illustration_sync(
                game_id=999,
                round_number=1,
                story_text="测试故事",
                character_settings={"era": "现代"},
                player_name="测试角色",
                existing_images=[
                    {
                        "image_id": 1,
                        "image_type": "character",
                        "entity_name": "测试角色",
                        "image_url": "http://example.com/img.jpg",
                    }
                ],
                stage="event",
                week=1,
            )

            # 验证文件存在
            scene = (
                db_session.query(SceneImage)
                .filter(SceneImage.game_id == 999, SceneImage.round_number == 1)
                .first()
            )
            assert scene is not None
            assert scene.storage_path is not None

            full_path = storage.get_full_path(str(scene.storage_path))
            assert os.path.exists(full_path), f"图片文件应保存到: {full_path}"

    def test_no_reference_direct_generate_saves_to_db(self, db_session):
        """没有参考图片时直接 generate，也应正确保存"""
        service = self._create_service(db_session)

        service.image_client.generate_image.return_value = (b"direct_image", "prompt")

        service._generate_round_illustration_sync(
            game_id=998,
            round_number=0,
            story_text="测试故事",
            character_settings={"era": "古代"},
            player_name="角色",
            existing_images=[],  # 没有参考图片
            stage="result",
            week=0,
        )

        scene = db_session.query(SceneImage).filter(SceneImage.game_id == 998).first()
        assert scene is not None
        assert scene.scene_description is not None

    def _create_service(self, db_session, storage=None):
        """创建带 mock image_client 的 RoundIllustrationService"""
        service = RoundIllustrationService.__new__(RoundIllustrationService)
        service.db = db_session
        service.image_client = MagicMock()
        # analyze_story_for_illustration 返回 (scene_desc, illustration_prompt)
        service.image_client.analyze_story_for_illustration.return_value = (
            "测试场景描述",
            "测试插画提示词",
        )
        service.image_storage = storage or ImageStorageService(local_path=Path(tempfile.mkdtemp()))
        return service
