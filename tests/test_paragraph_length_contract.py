"""Paragraph Length Contract Tests

验证故事生成提示词包含段落长度控制要求，防止生成超长段落。
Layer 3: 契约测试 — 提示词必须要求合理分段。
"""

from config.prompts import get_event_generation_prompt


class TestParagraphLengthContract:
    """测试段落长度控制契约"""

    def test_event_prompt_requires_paragraph_breaks(self):
        """事件生成提示词应包含分段要求"""
        player_state = {
            "age": 25,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "week": 5,
            "relationships": {},
            "decision_history": [],
        }
        prompt = get_event_generation_prompt(
            player_state=player_state,
            language="zh",
        )

        # 应包含段落长度控制要求
        has_paragraph_constraint = (
            "分段" in prompt
            or "换段" in prompt
            or "换行" in prompt
            or "paragraph" in prompt.lower()
        )
        assert has_paragraph_constraint, (
            f"事件生成提示词应包含段落控制要求。prompt前800字: {prompt[:800]}"
        )

    def test_english_event_prompt_requires_paragraph_breaks(self):
        """英文事件生成提示词应包含分段要求"""
        player_state = {
            "age": 25,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "week": 5,
            "relationships": {},
            "decision_history": [],
        }
        prompt = get_event_generation_prompt(
            player_state=player_state,
            language="en",
        )

        has_paragraph_constraint = "paragraph" in prompt.lower() or "break" in prompt.lower()
        assert has_paragraph_constraint, (
            f"英文事件生成提示词应包含段落控制要求。prompt前800字: {prompt[:800]}"
        )
