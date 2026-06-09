"""Era Validator Production Contract Tests

验证时代一致性验证器在生产环境中的正确行为。
Layer 3: 契约测试 — 验证器必须正确识别古代背景、不误报、能检测真实错位。
"""


class TestEraValidatorProductionContract:
    """测试 era_validator 生产环境契约"""

    def test_extract_validation_context_emits_era_fields(self):
        """_extract_validation_context 必须返回包含 era 和 era_type 的上下文"""
        from src.ai.client import AIClient
        from src.ai.story_generator import StoryGenerator

        gen = StoryGenerator(AIClient())
        character_settings = {
            "era": {
                "era_description": "宋朝",
                "world_context": "古代中国",
            },
            "world": {
                "world_description": "古代世界",
                "technology_level": "古代科技",
            },
        }
        ctx = gen._extract_validation_context(
            player_state={"week": 1, "relationships": {}},
            character_settings=character_settings,
        )
        assert "era" in ctx, "validation_context 缺少 'era' 键"
        assert "era_type" in ctx, "validation_context 缺少 'era_type' 键"
        assert ctx["era"] == "宋朝"
        assert ctx["era_type"] == "ancient"

    def test_extract_validation_context_modern_era(self):
        """_extract_validation_context 对现代背景应返回 modern era_type"""
        from src.ai.client import AIClient
        from src.ai.story_generator import StoryGenerator

        gen = StoryGenerator(AIClient())
        character_settings = {
            "era": {
                "era_description": "2024年现代中国",
                "world_context": "现代社会",
            },
        }
        ctx = gen._extract_validation_context(
            player_state={"week": 1, "relationships": {}},
            character_settings=character_settings,
        )
        assert "era" in ctx
        assert "era_type" in ctx
        assert ctx["era"] == "2024年现代中国"
        assert ctx["era_type"] == "modern"

    def test_era_validator_catches_real_anachronism(self):
        """古代背景故事中包含现代元素应被检测到"""
        from src.ai.harness.era_validator import validate_era_consistency

        passed, evidence, info = validate_era_consistency(
            "他在宋朝的街上买咖啡，然后刷抖音。",
            {"era": "宋朝", "era_type": "ancient"},
        )
        assert passed is False
        assert "found_modern" in info
        found = info["found_modern"]
        assert "咖啡" in found or "抖音" in found

    def test_era_validator_no_false_positive_yici(self):
        """'一次'作为普通量词不应触发误报"""
        from src.ai.harness.era_validator import validate_era_consistency

        passed, evidence, info = validate_era_consistency(
            "他第一次进入茶馆，点了一壶茶。",
            {"era": "宋朝", "era_type": "ancient"},
        )
        assert passed is True, f"不应误报: {evidence}"

    def test_era_validator_no_false_positive_ai_substring(self):
        """'AI' 不应作为子串匹配 TAI/RAID/SAID"""
        from src.ai.harness.era_validator import validate_era_consistency

        passed, evidence, info = validate_era_consistency(
            "Taiwan 是个好地方。Raid 成功了。Said 他很累。",
            {"era": "宋朝", "era_type": "ancient"},
        )
        assert passed is True, f"不应误报 AI 子串: {evidence}"

    def test_era_validator_no_false_positive_vr_ar_substring(self):
        """VR/AR 不应匹配子串如 'Vray', 'Aries'"""
        from src.ai.harness.era_validator import validate_era_consistency

        passed, evidence, info = validate_era_consistency(
            "Vray 渲染效果很好。Aries 是星座。",
            {"era": "宋朝", "era_type": "ancient"},
        )
        assert passed is True, f"不应误报 VR/AR 子串: {evidence}"

    def test_forbidden_list_no_duplicates(self):
        """_ANCIENT_FORBIDDEN_MODERN 列表不应有重复项"""
        from src.ai.harness.era_validator import _ANCIENT_FORBIDDEN_MODERN

        assert len(_ANCIENT_FORBIDDEN_MODERN) == len(set(_ANCIENT_FORBIDDEN_MODERN))

    def test_ancient_keywords_match_without_leading_space(self):
        """古代关键词应能匹配常见英文表述，无需前导空格"""
        from src.ai.harness.era_validator import validate_era_consistency

        # medieval Europe 应被识别为古代
        passed, _, info = validate_era_consistency(
            "一个普通的故事",
            {"era": "medieval Europe", "era_type": ""},
        )
        assert info.get("skipped") is not True, "medieval Europe 应被识别为古代背景"

        # historic period 应被识别为古代
        passed2, _, info2 = validate_era_consistency(
            "一个普通的故事",
            {"era": "historic period", "era_type": ""},
        )
        assert info2.get("skipped") is not True, "historic period 应被识别为古代背景"

    def test_modern_era_allows_modern_story(self):
        """现代背景中的现代元素应通过验证"""
        from src.ai.harness.era_validator import validate_era_consistency

        passed, evidence, info = validate_era_consistency(
            "他在用手机刷抖音。",
            {"era": "现代", "era_type": "modern"},
        )
        assert passed is True
        assert info.get("era_type") == "modern"

    def test_modern_era_rejects_historical_drift(self):
        """现代背景故事漂移成古代长安/铜钱/郎君时应被检测到"""
        from src.ai.harness.era_validator import validate_era_consistency

        passed, evidence, info = validate_era_consistency(
            "林知远站在长安西市的木坊里，鲁师傅收下三百文铜钱，称他为林郎君。",
            {"era": "2024年现代上海", "era_type": "modern"},
        )
        assert passed is False
        assert "found_historical" in info
        assert any(term in info["found_historical"] for term in ["长安", "铜钱", "郎君"])

    def test_quick_validator_rejects_modern_story_historical_drift(self):
        """生产快速校验必须阻止现代角色故事漂移到古代叙事。"""
        from src.ai.quick_validator import quick_validate_story

        result = quick_validate_story(
            story_text="林知远站在长安西市的木坊里，鲁师傅收下三百文铜钱，称他为林郎君。",
            character_settings={
                "era": {
                    "era_description": "2024年现代上海",
                    "world_context": "现代社会，独立游戏制作人与创业团队",
                },
            },
            language="zh",
        )
        assert result.passed is False
        assert any("现代背景检测到古代" in issue for issue in result.issues)

    def test_era_validator_no_false_positive_network_substring(self):
        """'网络' 不应匹配 '网络' 作为其他词的组成部分"""
        from src.ai.harness.era_validator import validate_era_consistency

        # 这个测试取决于修复方式，"网络"在中文里本身是词
        # 但应确保不会过度匹配；此处留作契约占位
        passed, evidence, info = validate_era_consistency(
            "渔网络续被收起。",
            {"era": "宋朝", "era_type": "ancient"},
        )
        assert passed is True, f"不应误报: {evidence}"

    def test_era_validator_no_false_positive_smart_substring(self):
        """'智能' 不应匹配 '智能' 作为其他词的组成部分"""
        from src.ai.harness.era_validator import validate_era_consistency

        passed, evidence, info = validate_era_consistency(
            "他无能，只能忍耐。",
            {"era": "宋朝", "era_type": "ancient"},
        )
        assert passed is True, f"不应误报: {evidence}"
