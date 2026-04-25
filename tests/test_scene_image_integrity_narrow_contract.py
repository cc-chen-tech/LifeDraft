"""SceneImage IntegrityError narrowing contract test.

验证 generate_round_scene_image 只捕获 UNIQUE 约束冲突的 IntegrityError，
其他类型的 IntegrityError（如外键违反、NOT NULL 违反）应重新抛出。
Layer 3: 契约测试
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from src.database.models import SceneImage
from src.services.image.scene_service import SceneImageService


class TestSceneImageIntegrityNarrowContract:
    """IntegrityError 捕获范围契约测试。"""

    def test_unique_constraint_conflict_returns_existing(self, db_session):
        """唯一约束冲突时应回滚并返回已有记录。

        模拟并发场景：pre-insert 查询返回 None（另一个线程尚未提交），
        但插入时触发唯一约束冲突，fallback 查询返回已有记录。
        """
        # 预置一条记录，使用真实存在的临时文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n")
            temp_path = f.name

        existing = SceneImage(
            game_id=10,
            week=0,
            round_number=1,
            stage="result",
            scene_description="已有",
            final_prompt="prompt",
            storage_path=temp_path,
            storage_type="local",
        )
        db_session.add(existing)
        db_session.commit()

        service = SceneImageService(db=db_session)

        with patch.object(
            service.image_client, "analyze_story_for_illustration"
        ) as mock_analyze, patch.object(
            service.image_client, "generate_image"
        ) as mock_generate, patch.object(
            service.storage_service, "save_image"
        ) as mock_save:

            mock_analyze.return_value = ("场景", "提示词")
            png_header = b"\x89PNG\r\n\x1a\n"
            mock_generate.return_value = (png_header + b"\x00" * 100, "prompt")
            mock_save.return_value = ("/tmp/new.png", "local")

            # 模拟 commit 时抛出包含 "UNIQUE constraint failed" 的 IntegrityError
            call_count = [0]
            original_commit = db_session.commit

            def side_effect_commit():
                call_count[0] += 1
                if call_count[0] == 1:
                    # 第一次 commit（删除旧记录）允许通过
                    original_commit()
                    return
                # 第二次 commit（插入新记录）触发唯一约束冲突
                raise IntegrityError(
                    "(sqlite3.IntegrityError) UNIQUE constraint failed: "
                    "scene_images.game_id, scene_images.week, "
                    "scene_images.round_number, scene_images.stage",
                    "",
                    "",
                )

            db_session.commit = side_effect_commit

            try:
                result = service.generate_round_scene_image(
                    game_id=10,
                    round_number=1,
                    story_text="测试",
                    character_settings={},
                    player_name="Test",
                    week=0,
                    stage="result",
                )
                assert result.scene_id == existing.scene_id
            finally:
                db_session.commit = original_commit
                os.unlink(temp_path)

    def test_non_unique_integrity_error_is_re_raised(self, db_session):
        """非唯一约束的 IntegrityError（如外键违反）应重新抛出，不应吞掉。"""
        service = SceneImageService(db=db_session)

        with patch.object(
            service.image_client, "analyze_story_for_illustration"
        ) as mock_analyze, patch.object(
            service.image_client, "generate_image"
        ) as mock_generate, patch.object(
            service.storage_service, "save_image"
        ) as mock_save:

            mock_analyze.return_value = ("场景", "提示词")
            png_header = b"\x89PNG\r\n\x1a\n"
            mock_generate.return_value = (png_header + b"\x00" * 100, "prompt")
            mock_save.return_value = ("/tmp/new.png", "local")

            # 模拟外键违反（不包含 "unique" 或 "duplicate" 关键词）
            db_session.commit = MagicMock(
                side_effect=IntegrityError(
                    "(sqlite3.IntegrityError) FOREIGN KEY constraint failed",
                    "",
                    "",
                )
            )

            try:
                from src.services.image import ImageServiceError
                with pytest.raises(ImageServiceError) as exc_info:
                    service.generate_round_scene_image(
                        game_id=999,
                        round_number=1,
                        story_text="测试",
                        character_settings={},
                        player_name="Test",
                        week=0,
                        stage="result",
                    )
                # 错误消息应包含原始错误信息，
                # 而非"无法获取或创建记录"
                err_str = str(exc_info.value)
                assert "FOREIGN KEY" in err_str or "数据库完整性错误" in err_str
            finally:
                # 恢复 db_session.commit
                db_session.rollback()
