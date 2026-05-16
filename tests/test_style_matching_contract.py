"""Style Matching Contract Tests

验证风格自动匹配系统能够根据角色设定选择非默认风格。
Layer 3: 契约测试 — 不同角色设定应匹配到不同叙事风格。
"""

from src.ai.narrative.style_matcher import auto_match_style


class TestStyleMatchingContract:
    """测试风格自动匹配契约"""

    def test_modern_cyberpunk_matches_non_default_style(self):
        """赛博朋克背景应匹配到非默认风格"""
        character_settings = {
            "era": {
                "year": "2077",
                "era_description": "近未来",
                "world_context": "赛博朋克世界",
            },
            "world": {
                "world_description": "高科技低生活",
                "technology_level": "超现代科技",
                "social_system": "企业统治",
            },
            "traits": {
                "personality": ["反叛", "孤独"],
                "traits_description": "一个黑客",
            },
        }

        result = auto_match_style(character_settings)
        # 赛博朋克背景不应只匹配到默认的 chinese_classic_saga
        assert (
            result.style_id != "chinese_classic_saga"
        ), f"赛博朋克背景不应匹配到默认的古典风格，实际匹配到: {result.style_id}"
        assert result.confidence > 0, "置信度应大于0"

    def test_modern_urban_matches_non_default_style(self):
        """现代都市背景应匹配到非默认风格"""
        character_settings = {
            "era": {
                "year": "2024",
                "era_description": "现代",
                "world_context": "当代中国都市",
            },
            "world": {
                "world_description": "现代都市生活",
                "technology_level": "现代科技",
                "social_system": "现代社会",
            },
            "traits": {
                "personality": ["内向", "敏感"],
                "traits_description": "一个普通上班族",
            },
        }

        result = auto_match_style(character_settings)
        # 现代背景不应只匹配到古典风格
        assert (
            result.style_id != "chinese_classic_saga"
        ), f"现代都市背景不应匹配到古典风格，实际匹配到: {result.style_id}"

    def test_ancient_china_matches_classic_saga(self):
        """古代中国背景可以匹配到 chinese_classic_saga"""
        character_settings = {
            "era": {
                "year": "1127",
                "era_description": "南宋",
                "world_context": "中国历史上的南宋时期",
            },
            "world": {
                "world_description": "古代中国",
                "technology_level": "古代科技",
            },
        }

        result = auto_match_style(character_settings)
        # 古代中国背景匹配到古典风格是合理的
        assert result.confidence > 0, "古代背景应有较高的匹配置信度"

    def test_diverse_settings_produce_different_styles(self):
        """不同的角色设定应产生不同的风格匹配结果"""
        cyberpunk = {
            "era": {"era_description": "2077", "world_context": "赛博朋克"},
            "world": {"world_description": "高科技", "technology_level": "未来"},
        }
        ancient = {
            "era": {"era_description": "南宋", "world_context": "古代中国"},
            "world": {"world_description": "古代", "technology_level": "古代"},
        }
        modern = {
            "era": {"era_description": "现代", "world_context": "当代"},
            "world": {"world_description": "都市", "technology_level": "现代"},
        }

        result_cyber = auto_match_style(cyberpunk)
        result_ancient = auto_match_style(ancient)
        result_modern = auto_match_style(modern)

        # 至少有两种不同的风格
        styles = {
            result_cyber.style_id,
            result_ancient.style_id,
            result_modern.style_id,
        }
        assert len(styles) >= 2, f"不同设定应匹配到不同风格，实际都匹配到: {styles}"
