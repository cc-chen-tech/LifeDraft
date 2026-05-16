"""Negative Prompt Contract Tests

验证图像生成的反向提示词包含反科幻/反时代错位约束。
Layer 3: 契约测试 — 反向提示词必须明确禁止科幻视觉元素。
"""

from src.ai.image_config import (DEFAULT_EDIT_NEGATIVE_PROMPT,
                                 DEFAULT_NEGATIVE_PROMPT)


class TestNegativePromptContract:
    """测试反向提示词包含反科幻约束"""

    def test_default_negative_prompt_bans_scifi(self):
        """DEFAULT_NEGATIVE_PROMPT 必须包含明确的科幻禁止词"""
        scifi_terms = [
            "赛博朋克",
            "cyberpunk",
            "科幻",
            "sci-fi",
            "science fiction",
            "金属质感",
            "metallic",
            "电路纹理",
            "circuit",
            "全息",
            "hologram",
            "发光",
            "glowing",
            "霓虹",
            "neon",
            "未来科技",
            "futuristic",
            "飞行汽车",
            "flying car",
            "机械义肢",
            "mechanical prosthetic",
            "电子眼",
            "cybernetic eye",
        ]
        assert any(
            term in DEFAULT_NEGATIVE_PROMPT.lower() for term in scifi_terms
        ), f"DEFAULT_NEGATIVE_PROMPT 应包含科幻禁止词。当前内容: {DEFAULT_NEGATIVE_PROMPT[:100]}..."

    def test_default_edit_negative_prompt_bans_scifi(self):
        """DEFAULT_EDIT_NEGATIVE_PROMPT 必须包含明确的科幻禁止词"""
        scifi_terms = [
            "赛博朋克",
            "cyberpunk",
            "科幻",
            "sci-fi",
            "金属质感",
            "metallic",
            "电路纹理",
            "circuit",
            "全息",
            "hologram",
            "发光",
            "glowing",
            "霓虹",
            "neon",
            "未来科技",
            "futuristic",
        ]
        assert any(
            term in DEFAULT_EDIT_NEGATIVE_PROMPT.lower() for term in scifi_terms
        ), f"DEFAULT_EDIT_NEGATIVE_PROMPT 应包含科幻禁止词。当前内容: {DEFAULT_EDIT_NEGATIVE_PROMPT[:100]}..."

    def test_modern_character_image_passes_scifi_negative_prompt(self):
        """现代人物肖像生成应传递包含反科幻约束的 negative_prompt"""
        from src.ai.image_client import ImageClient

        client = ImageClient.__new__(ImageClient)
        # 模拟内部组件
        from src.ai.image_generator import ImageGenerator
        from src.ai.image_prompt_builder import ImagePromptBuilder

        client._prompt_builder = ImagePromptBuilder()
        client._generator = ImageGenerator.__new__(ImageGenerator)

        # 拦截 generate_image 调用以检查参数
        captured = {}

        def mock_generate_image(prompt, size, style, quality, n, response_format, extra_params):
            captured["prompt"] = prompt
            captured["extra_params"] = extra_params
            return b"fake", prompt

        client._generator.generate_image = mock_generate_image

        # 调用现代人物生成
        client.generate_character_image(
            name="测试人物",
            description="一位28岁的中国男性",
            era="现代中国，2024年",
        )

        extra = captured.get("extra_params", {})
        negative = extra.get("negative_prompt", "")

        # 现代人物应有强反科幻反向提示词
        assert (
            "赛博朋克" in negative or "cyberpunk" in negative.lower()
        ), f"现代人物反向提示词应禁止赛博朋克。实际: {negative[:100]}..."
        assert (
            "科幻" in negative or "sci-fi" in negative.lower()
        ), f"现代人物反向提示词应禁止科幻。实际: {negative[:100]}..."

    def test_character_prompt_leads_with_realism_constraints(self):
        """人物prompt应以写实主义约束开头，确保模型优先关注"""
        from src.ai.image_prompt_builder import ImagePromptBuilder

        builder = ImagePromptBuilder()
        prompt = builder.build_character_prompt(
            name="李逍遥",
            description="一位28岁的中国男性",
            era="现代中国，2024年",
        )

        # 写实主义约束应在prompt的前30%位置内出现
        # 这样模型在生成初期就能看到约束
        first_third = len(prompt) // 3
        realism_section = prompt[:first_third]
        assert "写实主义" in realism_section or "禁止赛博朋克" in realism_section, (
            f"写实主义约束应位于prompt前1/3处以获得模型优先关注。"
            f"实际prompt前200字: {prompt[:200]}"
        )
