"""Scene edit negative prompt contract tests.

验证 scene_service 的 edit_image 调用传入场景专用的 negative_prompt。
Layer 3: 契约测试。
"""

from unittest.mock import MagicMock, patch
import pytest

pytestmark = [pytest.mark.unit]



class TestSceneEditNegativePrompt:
    """测试场景编辑使用专用 negative_prompt"""

    def test_scene_edit_negative_prompt_is_stronger_than_default(self):
        """SCENE_EDIT_NEGATIVE_PROMPT 应比 DEFAULT_EDIT_NEGATIVE_PROMPT 包含更多场景约束"""
        from src.ai.image_config import DEFAULT_EDIT_NEGATIVE_PROMPT
        from src.services.image.scene_service import SceneImageService

        scene_negative = SceneImageService.SCENE_EDIT_NEGATIVE_PROMPT

        assert (
            DEFAULT_EDIT_NEGATIVE_PROMPT in scene_negative
        ), "场景 negative_prompt 应基于默认 negative_prompt"
        assert "半身像" in scene_negative, "应包含场景约束：半身像"
        assert "特写" in scene_negative, "应包含场景约束：特写"
        assert "裁剪" in scene_negative, "应包含场景约束：裁剪"
        assert "多人重叠" in scene_negative, "应包含场景约束：多人重叠"
        assert "人物缺失" in scene_negative, "应包含场景约束：人物缺失"
        assert "遗漏人物" in scene_negative, "应包含场景约束：遗漏人物"
        assert len(scene_negative) > len(
            DEFAULT_EDIT_NEGATIVE_PROMPT
        ), "场景 negative_prompt 应比默认更长"

    def test_generate_round_scene_image_passes_scene_negative_prompt(self):
        """generate_round_scene_image 调用 edit_image 时应传入场景专用 negative_prompt"""
        from src.services.image.scene_service import SceneImageService

        service = SceneImageService.__new__(SceneImageService)
        service.db = MagicMock()
        # 让 db.query().filter().first() 返回 None，确保继续生成
        service.db.query.return_value.filter.return_value.first.return_value = None
        service.storage_service = MagicMock()
        service.storage_service.save_image.return_value = ("/tmp/test.png", "local")
        service.image_client = MagicMock()

        captured_calls = []

        def capture_edit_image(reference_image, prompt, size, num_images, extra_params=None):
            captured_calls.append(
                {
                    "reference_image": reference_image,
                    "prompt": prompt,
                    "size": size,
                    "num_images": num_images,
                    "extra_params": extra_params,
                }
            )
            return [(b"fake_image", "fake_prompt")]

        service.image_client.edit_image = capture_edit_image
        service.image_client.analyze_story_for_illustration = MagicMock(
            return_value=("scene desc", "illustration prompt")
        )
        service.image_client.generate_image = MagicMock(return_value=(b"fake_image", "fake_prompt"))

        # Mock _get_appearance_anchor to return None
        service._get_appearance_anchor = MagicMock(return_value=None)

        with patch.object(
            service,
            "_build_char_info",
            return_value={
                "era": "现代",
                "character_desc": "测试角色",
            },
        ):
            service.generate_round_scene_image(
                game_id=1,
                round_number=1,
                story_text="测试故事",
                character_settings={},
                player_name="测试玩家",
                player_image_id=1,
                week=0,
                get_player_image_func=lambda g, p: ("http://ref.png", 1),
            )

        assert len(captured_calls) == 1, "应调用一次 edit_image"
        actual_extra = captured_calls[0]["extra_params"]
        assert actual_extra is not None, "应传入 extra_params"
        assert "negative_prompt" in actual_extra, "extra_params 应包含 negative_prompt"
        assert "赛博朋克" in actual_extra["negative_prompt"], "negative_prompt 应包含反 sci-fi 约束"
        assert "多人重叠" in actual_extra["negative_prompt"], "negative_prompt 应包含场景特定约束"
