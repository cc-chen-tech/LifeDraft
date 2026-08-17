"""Punctuation Enforcement Contract Tests

验证故事生成 prompt 中包含强制使用正确标点的指令，防止 AI 输出缺少标点符号的文本。
Layer 3: 契约测试 — prompt 输出必须包含标点使用规范要求。
"""

from config.prompts import (get_event_generation_prompt,
                            get_result_generation_prompt,
                            get_round_event_prompt, get_story_only_prompt)
import pytest

pytestmark = [pytest.mark.unit]



class TestPunctuationEnforcementInPrompts:
    """测试故事生成 prompt 包含标点符号强制使用指令"""

    def _make_player_state(self):
        return {
            "age": 25,
            "week": 5,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
            "decision_history": [],
        }

    def test_story_only_prompt_has_punctuation_requirement(self):
        """get_story_only_prompt 必须包含强制正确使用标点的指令"""
        prompt = get_story_only_prompt(
            player_state=self._make_player_state(),
            language="zh",
        )
        # 必须包含对标点使用的明确要求
        has_punctuation_req = "标点" in prompt and (
            "必须使用" in prompt
            or "正确使用" in prompt
            or "规范使用" in prompt
            or "注意标点" in prompt
        )
        assert (
            has_punctuation_req
        ), f"prompt 必须包含强制正确使用标点的指令。prompt 前1000字: {prompt[:1000]}"

    def test_story_only_prompt_requires_quotation_marks_for_dialogue(self):
        """get_story_only_prompt 必须要求对话使用引号"""
        prompt = get_story_only_prompt(
            player_state=self._make_player_state(),
            language="zh",
        )
        # 必须要求对话使用中文引号 "" 或英文引号
        has_quote_req = '"' in prompt or '"' in prompt or "引号" in prompt
        assert has_quote_req, f"prompt 必须要求对话使用引号。prompt 前1000字: {prompt[:1000]}"

    def test_round_event_prompt_has_punctuation_requirement(self):
        """get_round_event_prompt 必须包含强制正确使用标点的指令"""
        prompt = get_round_event_prompt(
            player_state=self._make_player_state(),
            language="zh",
            round_number=0,
            round_context="",
        )
        has_punctuation_req = "标点" in prompt and (
            "必须使用" in prompt
            or "正确使用" in prompt
            or "规范使用" in prompt
            or "注意标点" in prompt
        )
        assert (
            has_punctuation_req
        ), f"round prompt 必须包含强制正确使用标点的指令。prompt 前1000字: {prompt[:1000]}"

    def test_event_generation_prompt_has_punctuation_requirement(self):
        """get_event_generation_prompt 必须包含强制正确使用标点的指令"""
        prompt = get_event_generation_prompt(
            player_state=self._make_player_state(),
            language="zh",
        )
        has_punctuation_req = "标点" in prompt and (
            "必须使用" in prompt
            or "正确使用" in prompt
            or "规范使用" in prompt
            or "注意标点" in prompt
        )
        assert (
            has_punctuation_req
        ), f"event generation prompt 必须包含强制正确使用标点的指令。prompt 前1000字: {prompt[:1000]}"

    def test_result_generation_prompt_has_punctuation_requirement(self):
        """get_result_generation_prompt 必须包含强制正确使用标点的指令"""
        prompt = get_result_generation_prompt(
            event_description="测试事件",
            chosen_option="选择A",
            effects={"energy": 10},
            language="zh",
        )
        has_punctuation_req = "标点" in prompt or "对话" in prompt or "引号" in prompt
        assert (
            has_punctuation_req
        ), f"result generation prompt 应包含标点或对话规范要求。prompt 前1000字: {prompt[:1000]}"

    def test_english_prompts_have_punctuation_requirement(self):
        """英文版 prompt 也必须包含标点规范要求"""
        prompt = get_story_only_prompt(
            player_state=self._make_player_state(),
            language="en",
        )
        has_punctuation_req = (
            "punctuation" in prompt.lower()
            or "quotation marks" in prompt.lower()
            or "dialogue" in prompt.lower()
        )
        assert (
            has_punctuation_req
        ), f"English prompt must contain punctuation or dialogue requirements. First 1000 chars: {prompt[:1000]}"
