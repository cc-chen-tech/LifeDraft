"""契约测试 — 场景插画 edit 失败降级到 generate

验证 illustration_service._generate_scene_image 在 edit_image 失败时，
自动降级到 generate_image，保证用户始终能看到场景插画。

测试层: 契约测试 (Layer 3)
目标: 验证 edit→generate 降级逻辑在 API 调用层面的正确性
可防止: 图生图 API 超时/失败时，用户完全看不到场景插画
"""

from unittest.mock import MagicMock, patch

from src.ai.image_exceptions import ImageGenerationError
from src.game.round.illustration_service import RoundIllustrationService


class TestImageEditFallbackContract:
    """契约测试：edit 失败降级到 generate"""

    def test_edit_failure_falls_back_to_generate(self):
        """edit_image 抛 ImageGenerationError 时，应自动降级到 generate_image"""
        service = MagicMock(spec=RoundIllustrationService)
        service.image_client = MagicMock()

        # edit_image 失败
        service.image_client.edit_image.side_effect = ImageGenerationError("API timeout")
        # generate_image 成功
        service.image_client.generate_image.return_value = (b"fake_image_data", "prompt_used")

        # 调用真实的方法逻辑（通过 patch 让 _generate_scene_image 使用真实代码）
        with patch.object(
            RoundIllustrationService, "_generate_scene_image", RoundIllustrationService._generate_scene_image
        ):
            result = RoundIllustrationService._generate_scene_image(
                self=service,
                scene_desc="一个年轻人在阳光下",
                illustration_prompt="写实风格",
                reference_urls=["data:image/jpeg;base64,abc123"],
                era="现代",
            )

        assert result[0] == b"fake_image_data", (
            f"edit 失败后应降级到 generate_image 并返回图片数据，"
            f"实际返回: {result}"
        )
        service.image_client.generate_image.assert_called_once()

    def test_edit_returns_empty_results_falls_back(self):
        """edit_image 返回空列表时，应自动降级到 generate_image"""
        service = MagicMock(spec=RoundIllustrationService)
        service.image_client = MagicMock()

        service.image_client.edit_image.return_value = []
        service.image_client.generate_image.return_value = (b"fallback_image", "prompt")

        with patch.object(
            RoundIllustrationService, "_generate_scene_image", RoundIllustrationService._generate_scene_image
        ):
            result = RoundIllustrationService._generate_scene_image(
                self=service,
                scene_desc="战斗场景",
                illustration_prompt="武侠风格",
                reference_urls=["data:image/jpeg;base64,abc123"],
                era="古代",
            )

        assert result[0] == b"fallback_image"
        service.image_client.generate_image.assert_called_once()

    def test_no_reference_urls_uses_generate_directly(self):
        """没有 reference_urls 时，直接调用 generate_image（无需降级）"""
        service = MagicMock(spec=RoundIllustrationService)
        service.image_client = MagicMock()
        service.image_client.generate_image.return_value = (b"direct_image", "prompt")

        with patch.object(
            RoundIllustrationService, "_generate_scene_image", RoundIllustrationService._generate_scene_image
        ):
            result = RoundIllustrationService._generate_scene_image(
                self=service,
                scene_desc="风景",
                illustration_prompt="山水画风格",
                reference_urls=[],
                era="古代",
            )

        assert result[0] == b"direct_image"
        service.image_client.generate_image.assert_called_once()
        service.image_client.edit_image.assert_not_called()

    def test_edit_success_no_fallback(self):
        """edit_image 成功时，不应调用 generate_image"""
        service = MagicMock(spec=RoundIllustrationService)
        service.image_client = MagicMock()

        service.image_client.edit_image.return_value = [(b"edited_image", "edit_prompt")]

        with patch.object(
            RoundIllustrationService, "_generate_scene_image", RoundIllustrationService._generate_scene_image
        ):
            result = RoundIllustrationService._generate_scene_image(
                self=service,
                scene_desc="场景",
                illustration_prompt="prompt",
                reference_urls=["data:image/jpeg;base64,abc123"],
                era="现代",
            )

        assert result[0] == b"edited_image"
        service.image_client.edit_image.assert_called_once()
        service.image_client.generate_image.assert_not_called()

    def test_content_inspection_error_not_fallback(self):
        """内容审核错误不应降级（降级也无意义，prompt 本身有问题）"""
        from src.ai.image_exceptions import ContentInspectionError

        service = MagicMock(spec=RoundIllustrationService)
        service.image_client = MagicMock()
        service.image_client.edit_image.side_effect = ContentInspectionError(
            "内容审核未通过", original_prompt="test"
        )

        with patch.object(
            RoundIllustrationService, "_generate_scene_image", RoundIllustrationService._generate_scene_image
        ):
            try:
                RoundIllustrationService._generate_scene_image(
                    self=service,
                    scene_desc="场景",
                    illustration_prompt="prompt",
                    reference_urls=["data:image/jpeg;base64,abc123"],
                    era="现代",
                )
                assert False, "应抛出 ContentInspectionError"
            except ContentInspectionError:
                pass  # 预期行为

        service.image_client.generate_image.assert_not_called()
