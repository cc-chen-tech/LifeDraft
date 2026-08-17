"""Character image generation extra_params propagation tests.
import pytest

pytestmark = [pytest.mark.unit]


验证 generate_character_images() 正确传递 extra_params 到底层 API 调用。
"""


class TestCharacterImageExtraParamsPropagation:
    """测试 generate_character_images() 传递 extra_params"""

    def test_generate_character_images_passes_extra_params(
        self,
    ):
        """extra_params 应传递给 generate_image_with_url()"""
        from src.ai.image_generator import ImageGenerator

        gen = ImageGenerator.__new__(ImageGenerator)
        gen.text_to_image_models = ["qwen-image-max"]
        gen.image_edit_models = ["qwen-image-edit"]
        gen.max_retries = 1

        captured_calls = []

        def mock_generate_image_with_url(prompt, size, extra_params=None):
            captured_calls.append({"prompt": prompt, "extra_params": extra_params})
            # 返回 (bytes, prompt, url)
            return b"fake", prompt, "http://fake.url/image.jpg"

        def mock_edit_image(reference_image, prompt, size, num_images):
            return [(b"fake_edited", prompt)]

        gen.generate_image_with_url = mock_generate_image_with_url
        gen.edit_image = mock_edit_image

        from src.ai.image_prompt_builder import ImagePromptBuilder

        prompt_builder = ImagePromptBuilder()
        test_negative = "赛博朋克，科幻，金属质感"

        # 调用 generate_character_images 并传入 extra_params
        gen.generate_character_images(
            name="测试人物",
            description="一位28岁的中国男性",
            era="现代中国，2024年",
            num_images=1,
            prompt_builder=prompt_builder,
            extra_params={"negative_prompt": test_negative},
        )

        assert len(captured_calls) >= 1, "应至少调用一次 generate_image_with_url"
        actual_extra = captured_calls[0].get("extra_params", {})
        actual_negative = actual_extra.get("negative_prompt", "")

        assert test_negative in actual_negative, (
            f"extra_params 中的 negative_prompt 应传递到 generate_image_with_url。"
            f"实际接收到: {actual_negative}"
        )

    def test_generate_character_images_without_extra_params_uses_default(self):
        """不传 extra_params 时应使用默认参数（不报错）"""
        from src.ai.image_generator import ImageGenerator

        gen = ImageGenerator.__new__(ImageGenerator)
        gen.text_to_image_models = ["qwen-image-max"]
        gen.image_edit_models = ["qwen-image-edit"]
        gen.max_retries = 1

        captured_calls = []

        def mock_generate_image_with_url(prompt, size, extra_params=None):
            captured_calls.append({"extra_params": extra_params})
            return b"fake", prompt, "http://fake.url/image.jpg"

        def mock_edit_image(reference_image, prompt, size, num_images):
            return [(b"fake_edited", prompt)]

        gen.generate_image_with_url = mock_generate_image_with_url
        gen.edit_image = mock_edit_image

        from src.ai.image_prompt_builder import ImagePromptBuilder

        prompt_builder = ImagePromptBuilder()

        # 不传递 extra_params
        gen.generate_character_images(
            name="测试人物",
            description="一位28岁的中国男性",
            era="现代中国，2024年",
            num_images=1,
            prompt_builder=prompt_builder,
        )

        assert len(captured_calls) >= 1
        # 不传时不应报错，extra_params 可以为 None 或空 dict
