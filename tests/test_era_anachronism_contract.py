"""Era Anachronism Prevention Contract Tests

验证事件生成提示词包含时代错位预防措施。
Layer 3: 契约测试 — 提示词中必须包含针对角色时代的明确禁止词列表。
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestEraAnachronismContract:
    """测试时代错位预防 API 契约"""

    def test_ancient_era_prompt_has_forbidden_modern_terms(self):
        """古代背景提示词应包含明确的现代禁止词列表"""
        from config.prompts.story_prompts import get_event_generation_prompt

        player_state = {
            "age": 22,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "week": 5,
            "relationships": {},
            "decision_history": [],
        }
        character_settings = {
            "era": {
                "year": "1127",
                "era_description": "南宋",
                "world_context": "中国历史上的南宋时期",
            },
            "age": {"age": 22, "age_description": "青年"},
            "gender": {"gender": "男"},
            "world": {"world_description": "古代中国", "technology_level": "古代科技"},
        }

        prompt = get_event_generation_prompt(
            player_state=player_state,
            language="zh",
            character_settings=character_settings,
        )

        # 提示词中应包含时代约束相关内容
        assert "时代" in prompt or "era" in prompt.lower()
        # 应包含明确的现代概念禁止列表
        forbidden_terms = ["手机", "电脑", "汽车", "飞机", "电话", "电梯", "星巴克", "咖啡", "互联网", "微信", "地铁", "高铁"]
        assert any(term in prompt for term in forbidden_terms), (
            f"古代背景提示词应包含明确的现代禁止词列表。实际提示词中未找到: {forbidden_terms}"
        )

    def test_english_ancient_era_prompt_has_forbidden_modern_terms(self):
        """英文古代背景提示词应包含明确的现代禁止词列表"""
        from config.prompts.story_prompts import get_event_generation_prompt

        player_state = {
            "age": 22,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "week": 5,
            "relationships": {},
            "decision_history": [],
        }
        character_settings = {
            "era": {
                "year": "1127",
                "era_description": "Southern Song Dynasty",
                "world_context": "Ancient China",
            },
            "age": {"age": 22, "age_description": "Young adult"},
            "gender": {"gender": "Male"},
            "world": {"world_description": "Ancient China", "technology_level": "Ancient"},
        }

        prompt = get_event_generation_prompt(
            player_state=player_state,
            language="en",
            character_settings=character_settings,
        )

        # 应包含明确的现代概念禁止列表
        forbidden_terms = ["phone", "computer", "car", "airplane", "internet", "elevator", "starbucks", "coffee shop", "subway"]
        assert any(term in prompt.lower() for term in forbidden_terms), (
            f"英文古代背景提示词应包含明确的现代禁止词列表。实际提示词中未找到: {forbidden_terms}"
        )

    def test_modern_era_does_not_over_restrict(self):
        """现代背景不应过度限制现代概念"""
        from config.prompts.story_prompts import get_event_generation_prompt

        player_state = {
            "age": 22,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "week": 5,
            "relationships": {},
            "decision_history": [],
        }
        character_settings = {
            "era": {
                "year": "2024",
                "era_description": "现代",
                "world_context": "现代社会",
            },
            "age": {"age": 22, "age_description": "青年"},
            "gender": {"gender": "男"},
            "world": {"world_description": "现代世界", "technology_level": "现代科技"},
        }

        prompt = get_event_generation_prompt(
            player_state=player_state,
            language="zh",
            character_settings=character_settings,
        )

        # 现代背景不应包含对现代概念的禁止列表
        forbidden_terms = ["手机", "电脑", "汽车", "星巴克", "互联网"]
        # 这些词不应出现在"禁止"上下文中
        for term in forbidden_terms:
            # 如果这个词出现，它不应该在"禁止"附近
            idx = prompt.find(term)
            if idx != -1:
                context = prompt[max(0, idx - 20):idx + 20]
                assert "禁止" not in context, f"现代背景不应禁止'{term}'，但上下文中出现了禁止: {context}"

    def test_era_anachronism_helper_exists(self):
        """EraConstraintBuilder 辅助函数应存在"""
        from config.prompts._helpers import _build_era_anachronism_constraints
        # 古代背景应返回包含禁止词的约束文本
        result = _build_era_anachronism_constraints(
            {"era": {"era_description": "南宋", "world_context": "古代中国"}},
            "zh"
        )
        assert "手机" in result or "phone" in result.lower()
        assert "电脑" in result or "computer" in result.lower()

        # 现代背景应返回较宽松的约束
        result_modern = _build_era_anachronism_constraints(
            {"era": {"era_description": "现代", "world_context": "现代社会"}},
            "zh"
        )
        # 现代背景不应禁止手机/电脑
        assert "手机" not in result_modern
        assert "电脑" not in result_modern
