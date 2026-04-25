"""Choice Impact Contract Tests

验证故事生成提示词包含足够的分支影响说明，防止不同选择导致相同走向。
Layer 3: 契约测试 — 结果生成提示词必须要求选择产生独特影响。
"""

from config.prompts import get_result_generation_prompt


class TestChoiceImpactContract:
    """测试选择分支影响契约"""

    def test_result_prompt_requires_unique_impact(self):
        """结果生成提示词必须要求选择产生独特影响"""
        prompt = get_result_generation_prompt(
            event_description="主角面临一个职业选择",
            chosen_option="接受外派任务",
            effects={"wealth": 5000, "mood": -10},
            language="zh",
        )

        # 应包含要求选择产生独特/不同影响的指令
        assert "独特" in prompt or "不同" in prompt or "unique" in prompt.lower() or "distinct" in prompt.lower(), (
            f"结果生成提示词应要求选择产生独特影响。prompt前500字: {prompt[:500]}"
        )

    def test_result_prompt_requires_paragraph_breaks(self):
        """结果生成提示词应包含分段要求"""
        prompt = get_result_generation_prompt(
            event_description="主角面临一个职业选择",
            chosen_option="接受外派任务",
            effects={"wealth": 5000, "mood": -10},
            language="zh",
        )

        # 应包含段落长度控制要求
        assert "段" in prompt or "paragraph" in prompt.lower() or "换行" in prompt or "换段" in prompt, (
            f"结果生成提示词应包含分段要求。prompt前500字: {prompt[:500]}"
        )

    def test_english_result_prompt_requires_unique_impact(self):
        """英文结果生成提示词必须要求选择产生独特影响"""
        prompt = get_result_generation_prompt(
            event_description="The protagonist faces a career choice",
            chosen_option="Accept the overseas assignment",
            effects={"wealth": 5000, "mood": -10},
            language="en",
        )

        assert "unique" in prompt.lower() or "distinct" in prompt.lower() or "different" in prompt.lower(), (
            f"英文结果生成提示词应要求选择产生独特影响。prompt前500字: {prompt[:500]}"
        )
