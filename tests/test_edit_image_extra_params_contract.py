"""edit_image extra_params propagation contract tests.

验证 edit_image() 正确传递 extra_params（尤其是 negative_prompt）到底层 API。
Layer 3: 契约测试。
"""

from unittest.mock import MagicMock


class TestEditImageExtraParamsPropagation:
    """测试 edit_image 传递 extra_params"""

    def test_edit_image_includes_default_negative_prompt(self):
        """edit_image 应在 API 请求中包含默认 negative_prompt"""
        from src.ai.image_config import DEFAULT_EDIT_NEGATIVE_PROMPT
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
                    "choices": [{"message": {"content": [{"image": "http://test/image.png"}]}}]
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
        assert actual_negative == DEFAULT_EDIT_NEGATIVE_PROMPT, (
            f"API 请求应包含默认 negative_prompt。" f"实际: {actual_negative}"
        )

    def test_edit_image_without_extra_params_uses_default(self):
        """不传 extra_params 时应使用默认 negative_prompt"""
        from src.ai.image_config import DEFAULT_EDIT_NEGATIVE_PROMPT
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
                    "choices": [{"message": {"content": [{"image": "http://test/image.png"}]}}]
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
            f"不传 extra_params 时应使用 DEFAULT_EDIT_NEGATIVE_PROMPT。" f"实际: {actual_negative}"
        )

    def test_edit_image_payload_structure(self):
        """edit_image API 请求体应包含正确的参数结构"""
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
                    "choices": [{"message": {"content": [{"image": "http://test/image.png"}]}}]
                }
            }
            return resp

        gen.session.post = mock_post
        gen._download_image = lambda url: b"fake_image"

        gen.edit_image(
            reference_image="http://ref.png",
            prompt="test prompt",
        )

        assert len(captured_payloads) == 1
        params = captured_payloads[0]["parameters"]
        assert "n" in params
        assert "size" in params
        assert "negative_prompt" in params
        assert "prompt_extend" in params
        assert "watermark" in params

    def test_edit_image_extra_params_override_negative_prompt(self):
        """extra_params 应能覆盖默认 negative_prompt"""
        from src.ai.image_config import DEFAULT_EDIT_NEGATIVE_PROMPT
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
                    "choices": [{"message": {"content": [{"image": "http://test/image.png"}]}}]
                }
            }
            return resp

        gen.session.post = mock_post
        gen._download_image = lambda url: b"fake_image"

        custom_negative = DEFAULT_EDIT_NEGATIVE_PROMPT + "，额外限制"
        gen.edit_image(
            reference_image="http://ref.png",
            prompt="test prompt",
            extra_params={"negative_prompt": custom_negative},
        )

        assert len(captured_payloads) == 1
        actual_negative = captured_payloads[0]["parameters"]["negative_prompt"]
        assert custom_negative == actual_negative, (
            f"extra_params 应覆盖默认 negative_prompt。"
            f"期望: {custom_negative}，实际: {actual_negative}"
        )
