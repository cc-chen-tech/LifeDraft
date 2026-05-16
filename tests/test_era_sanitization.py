"""Era description sanitization tests.

验证图像生成前 era 描述中的科幻暗示词被清洗。
"""


class TestEraSanitization:
    """测试 era 描述清洗"""

    def test_build_character_prompt_sanitizes_scifi_era_words(self):
        """build_character_prompt 应对 era 中的科幻词汇进行清洗"""
        from src.ai.image_prompt_builder import ImagePromptBuilder

        builder = ImagePromptBuilder()
        scifi_era = (
            "这是一个数字化与实体交融的时代，全球互联互通达到新高度，"
            "人工智能与可持续发展成为主旋律。科技飞速进步的同时，"
            "虚拟现实与全息投影成为日常生活的一部分。"
        )

        prompt = builder.build_character_prompt(
            name="测试人物",
            description="一位普通的现代青年",
            era=scifi_era,
        )

        # prompt 中的【时代背景】不应包含科幻暗示词
        scifi_keywords = ["人工智能", "数字化", "虚拟现实", "全息投影", "科技飞速进步"]
        era_section_start = prompt.find("【时代背景】")
        era_section_end = prompt.find("【外貌特征】")
        era_section = prompt[era_section_start:era_section_end]

        for kw in scifi_keywords:
            assert kw not in era_section, (
                f"时代背景段落不应包含科幻暗示词 '{kw}'。" f"实际 era 段落: {era_section[:100]}"
            )

    def test_build_character_prompt_preserves_temporal_context(self):
        """清洗后应保留基本的时间/地点信息"""
        from src.ai.image_prompt_builder import ImagePromptBuilder

        builder = ImagePromptBuilder()
        era = "2024年中国，现代都市"

        prompt = builder.build_character_prompt(
            name="测试人物",
            description="一位普通的现代青年",
            era=era,
        )

        assert (
            "2024" in prompt or "现代" in prompt or "中国" in prompt
        ), f"清洗不应删除基本时间地点信息。prompt: {prompt[:200]}"

    def test_sanitize_era_helper_exists(self):
        """应存在 era 清洗辅助函数"""
        from src.ai.image_prompt_builder import ImagePromptBuilder

        builder = ImagePromptBuilder()
        assert hasattr(
            builder, "_sanitize_era_for_image"
        ), "ImagePromptBuilder 应有 _sanitize_era_for_image 方法"
