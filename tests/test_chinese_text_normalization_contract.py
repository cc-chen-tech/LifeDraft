"""Chinese Text Normalization Contract Tests
import pytest

pytestmark = [pytest.mark.unit]


验证标点规范化后处理在故事生成管道中正确执行。
Layer 3: 契约测试 — 输出文本必须规范。

注意：_normalize_punctuation 在 v2 中重构为 StoryGenerator 的 @staticmethod，
繁简转换（opencc）逻辑已移除，因为 AI 模型已原生输出简体中文。
"""


class TestChineseTextNormalizationContract:
    """测试中文文本规范化契约"""

    @staticmethod
    def _normalize(text: str, language: str = "zh") -> str:
        from src.ai.story_generator import StoryGenerator

        return StoryGenerator._normalize_punctuation(text, language)

    def test_chinese_punctuation_converted(self):
        """中文模式下标点符号转换为中文标点"""
        text = "Hello, world. How are you?"
        normalized = self._normalize(text, language="zh")
        assert "，" in normalized, "英文逗号应转换为中文逗号"
        assert "。" in normalized, "英文句号应转换为中文句号"
        assert "？" in normalized, "英文问号应转换为中文问号"

    def test_chinese_brackets_converted(self):
        """中文模式下括号转换为中文括号"""
        text = "He (the doctor) said"
        normalized = self._normalize(text, language="zh")
        assert "（" in normalized, "英文左括号应转换为中文左括号"
        assert "）" in normalized, "英文右括号应转换为中文右括号"

    def test_chinese_quotes_alternating(self):
        """中文模式下英文引号应转换为交替的中文引号"""
        text = '"Hello" and "World"'
        normalized = self._normalize(text, language="zh")
        assert "“" in normalized, "应有左引号"
        assert "”" in normalized, "应有右引号"
        assert normalized.count("“") == 2
        assert normalized.count("”") == 2

    def test_chinese_ellipsis_normalized(self):
        """英文句点序列在中文模式下转为中文句号序列"""
        text = "He paused... then spoke"
        normalized = self._normalize(text, language="zh")
        assert "。。。" in normalized, "英文句点应转为中文句号"
        assert normalized.count("。") == 3

    def test_double_dot_ellipsis_normalized(self):
        """双点转为两个中文句号"""
        text = "He paused.. then spoke"
        normalized = self._normalize(text, language="zh")
        assert "。。" in normalized
        assert normalized.count("。") == 2

    def test_english_language_skipped(self):
        """英文模式下标点不转换"""
        text = "Hello, world. How are you?"
        normalized = self._normalize(text, language="en")
        assert normalized == text, "英文模式下不应修改文本"

    def test_empty_text_preserved(self):
        """空文本保持不变"""
        assert self._normalize("", language="zh") == ""
        assert self._normalize(None, language="zh") is None  # type: ignore[arg-type]

    def test_trailing_spaces_cleaned(self):
        """中文标点后多余空格应清理"""
        text = "他说： 你好， 世界。"
        normalized = self._normalize(text, language="zh")
        assert "： " not in normalized, "冒号后空格应清除"
        assert "， " not in normalized, "逗号后空格应清除"

    def test_chinese_ellipsis_dots_normalized(self):
        """中文句号省略号保持为中文句号序列"""
        text = "他沉默了。。。不知该说什么"
        normalized = self._normalize(text, language="zh")
        assert "。。。" in normalized
        assert "……" not in normalized

    def test_already_chinese_punctuation_preserved(self):
        """已是中文标点保持不变"""
        text = "你好，世界。今天天气真好！"
        normalized = self._normalize(text, language="zh")
        assert "。" in normalized
        assert "！" in normalized

    def test_era_anachronism_caught_by_validator(self):
        """时代一致性验证器应检测古代背景中的现代元素"""
        from src.ai.harness.era_validator import validate_era_consistency

        story = "在唐朝的街道上，李逍遥走进星巴克，点了一杯拿铁"
        context = {"era": "唐朝", "era_type": "ancient"}
        passed, evidence, details = validate_era_consistency(story, context)
        assert not passed, "应检测到现代元素 '星巴克'"
        assert "星巴克" in evidence or "现代" in evidence

    def test_modern_era_no_false_positive(self):
        """现代背景下不应误报"""
        from src.ai.harness.era_validator import validate_era_consistency

        story = "李逍遥走进星巴克，点了一杯拿铁"
        context = {"era": "现代", "era_type": "modern"}
        passed, evidence, details = validate_era_consistency(story, context)
        assert passed, "现代背景不应触发时代穿越警告"

    def test_decision_history_prompt_includes_30_entries(self):
        """决策历史 prompt 应包含最多30条"""
        from config.prompts.story_prompts import get_event_generation_prompt

        decision_history = [
            {"week": i, "choice": f"选择{i}", "event": f"事件{i}" * 10} for i in range(31)
        ]
        player_state = {
            "age": 25,
            "week": 31,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
            "decision_history": decision_history,
        }
        prompt = get_event_generation_prompt(
            player_state=player_state,
            language="zh",
        )
        assert "选择25" in prompt or "事件25" in prompt, "应包含第25条决策历史"
        assert "事件20" in prompt, "应包含第20条决策历史"
