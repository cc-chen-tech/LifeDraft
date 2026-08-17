"""edit_image MiniMax payload contract tests.

验证 edit_image() 使用 MiniMax subject_reference 契约，并只把显式 negative_prompt 合并到 prompt。
Layer 3: 契约测试。
"""

from unittest.mock import MagicMock
import pytest

pytestmark = [pytest.mark.unit]



class TestEditImageExtraParamsPropagation:
    """测试 edit_image 传递 extra_params"""

    def test_edit_image_uses_minimax_subject_reference(self):
        """edit_image 应使用 MiniMax subject_reference，而不是旧 input.messages 结构"""
        from src.ai.image_generator import ImageGenerator

        gen = ImageGenerator.__new__(ImageGenerator)
        gen.image_edit_models = ["image-01"]
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
                "data": {"image_urls": ["http://test/image.png"]},
                "base_resp": {"status_code": 0, "status_msg": "success"},
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
        body = captured_payloads[0]
        assert body["model"] == "image-01"
        assert body["prompt"] == "test prompt"
        assert body["subject_reference"] == [
            {"type": "character", "image_file": "http://ref.png"}
        ]
        assert "input" not in body
        assert "parameters" not in body
        assert "negative_prompt" not in body

    def test_edit_image_without_extra_params_does_not_send_unsupported_negative_field(self):
        """不传 extra_params 时不应发送 MiniMax 不支持的 negative_prompt 字段"""
        from src.ai.image_generator import ImageGenerator

        gen = ImageGenerator.__new__(ImageGenerator)
        gen.image_edit_models = ["image-01"]
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
                "data": {"image_urls": ["http://test/image.png"]},
                "base_resp": {"status_code": 0, "status_msg": "success"},
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
        assert "negative_prompt" not in captured_payloads[0]
        assert "Avoid:" not in captured_payloads[0]["prompt"]

    def test_edit_image_payload_structure(self):
        """edit_image API 请求体应包含 MiniMax 支持的参数结构"""
        from src.ai.image_generator import ImageGenerator

        gen = ImageGenerator.__new__(ImageGenerator)
        gen.image_edit_models = ["image-01"]
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
                "data": {"image_urls": ["http://test/image.png"]},
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
            return resp

        gen.session.post = mock_post
        gen._download_image = lambda url: b"fake_image"

        gen.edit_image(
            reference_image="http://ref.png",
            prompt="test prompt",
        )

        assert len(captured_payloads) == 1
        body = captured_payloads[0]
        assert "n" in body
        assert "aspect_ratio" in body
        assert "response_format" in body
        assert "prompt_optimizer" in body
        assert "aigc_watermark" not in body
        assert "subject_reference" in body

    def test_edit_image_extra_params_negative_prompt_is_folded_into_prompt(self):
        """MiniMax 不支持 negative_prompt 字段，应把显式 negative_prompt 合并进 prompt"""
        from src.ai.image_generator import ImageGenerator

        gen = ImageGenerator.__new__(ImageGenerator)
        gen.image_edit_models = ["image-01"]
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
                "data": {"image_urls": ["http://test/image.png"]},
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
            return resp

        gen.session.post = mock_post
        gen._download_image = lambda url: b"fake_image"

        custom_negative = "额外限制"
        gen.edit_image(
            reference_image="http://ref.png",
            prompt="test prompt",
            extra_params={"negative_prompt": custom_negative},
        )

        assert len(captured_payloads) == 1
        body = captured_payloads[0]
        assert "negative_prompt" not in body
        assert body["prompt"] == "test prompt\nAvoid: 额外限制"
