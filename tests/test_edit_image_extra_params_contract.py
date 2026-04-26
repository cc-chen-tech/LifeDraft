"""edit_image extra_params propagation contract tests.

验证 edit_image() 正确传递 extra_params（尤其是 negative_prompt）到底层 API。
Layer 3: 契约测试。
"""

from unittest.mock import MagicMock


class TestEditImageExtraParamsPropagation:
    """测试 edit_image 传递 extra_params"""

    def test_edit_image_passes_negative_prompt_via_extra_params(self):
        """edit_image 应通过 extra_params 传递自定义 negative_prompt"""
        from src.ai.image_generator import ImageGenerator

        gen = ImageGenerator.__new__(ImageGenerator)
        gen.image_edit_models = ["qwen-image-edit"]
        gen.api_key = "test-key"
        gen.base_url = "https://test"
        gen.timeout = 30
        gen.max_retries = 1
        gen.session = MagicMock()

        captured_payloads = []

        def mock_post(url, json=None, headers=None, timeout=None):
            captured_payloads.append(json)
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "output": {
                    "choices": [
                        {
                            "message": {
                                "content": [{"image": "http://test/image.png"}]
                            }
                        }
                    ]
                }
            }
            return resp

        gen.session.post = mock_post
        gen._download_image = lambda url: b"fake_image"

        custom_negative = "赛博朋克，科幻，发光效果，测试专用"

        gen.edit_image(
            reference_image="http://ref.png",
            prompt="test prompt",
            size="1664*928",
            num_images=1,
            extra_params={"negative_prompt": custom_negative},
        )

        assert len(captured_payloads) == 1
        actual_negative = captured_payloads[0]["parameters"]["negative_prompt"]
        assert custom_negative in actual_negative, (
            f"自定义 negative_prompt 应传递到 API 请求。"
            f"实际: {actual_negative}"
        )

    def test_edit_image_without_extra_params_uses_default(self):
        """不传 extra_params 时应使用默认 negative_prompt"""
        from src.ai.image_generator import ImageGenerator
        from src.ai.image_config import DEFAULT_EDIT_NEGATIVE_PROMPT

        gen = ImageGenerator.__new__(ImageGenerator)
        gen.image_edit_models = ["qwen-image-edit"]
        gen.api_key = "test-key"
        gen.base_url = "https://test"
        gen.timeout = 30
        gen.max_retries = 1
        gen.session = MagicMock()

        captured_payloads = []

        def mock_post(url, json=None, headers=None, timeout=None):
            captured_payloads.append(json)
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "output": {
                    "choices": [
                        {
                            "message": {
                                "content": [{"image": "http://test/image.png"}]
                            }
                        }
                    ]
                }
            }
            return resp

        gen.session.post = mock_post
        gen._download_image = lambda url: b"fake_image"

        gen.edit_image(
            reference_image="http://ref.png",
            prompt="test prompt",
            size="1664*928",
            num_images=1,
        )

        assert len(captured_payloads) == 1
        actual_negative = captured_payloads[0]["parameters"]["negative_prompt"]
        assert DEFAULT_EDIT_NEGATIVE_PROMPT == actual_negative, (
            f"不传 extra_params 时应使用 DEFAULT_EDIT_NEGATIVE_PROMPT。"
            f"实际: {actual_negative}"
        )

    def test_edit_image_passes_seed_via_extra_params(self):
        """edit_image 应通过 extra_params 传递 seed"""
        from src.ai.image_generator import ImageGenerator

        gen = ImageGenerator.__new__(ImageGenerator)
        gen.image_edit_models = ["qwen-image-edit"]
        gen.api_key = "test-key"
        gen.base_url = "https://test"
        gen.timeout = 30
        gen.max_retries = 1
        gen.session = MagicMock()

        captured_payloads = []

        def mock_post(url, json=None, headers=None, timeout=None):
            captured_payloads.append(json)
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "output": {
                    "choices": [
                        {
                            "message": {
                                "content": [{"image": "http://test/image.png"}]
                            }
                        }
                    ]
                }
            }
            return resp

        gen.session.post = mock_post
        gen._download_image = lambda url: b"fake_image"

        gen.edit_image(
            reference_image="http://ref.png",
            prompt="test prompt",
            extra_params={"seed": 42},
        )

        assert len(captured_payloads) == 1
        assert captured_payloads[0]["parameters"]["seed"] == 42
