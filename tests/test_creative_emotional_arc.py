"""EmotionalArcAnalyzer 情感弧线分析器 单元测试

L3 创意增强层 - 情感弧线追踪与干预
模块尚未实现，测试应为红色（TDD先行）
"""

import pytest

from src.ai.creative.emotional_arc import EmotionalArcAnalyzer, EmotionalArcResult


# --------------- 测试数据 ---------------

JOYFUL_TEXT = "阳光洒满庭院，少女轻笑着追逐蝴蝶，花瓣在微风中翩翩起舞，一切都如梦般美好。"
TENSE_TEXT = "黑暗中传来低沉的脚步声，他屏住呼吸，手心满是冷汗，门把手缓缓转动——"
CATHARSIS_TEXT = "泪水终于夺眶而出，多年的恩怨在这一刻烟消云散，他紧紧握住对方的手，再也不愿松开。"
FLAT_TEXT_1 = "他走进房间，坐下来，喝了口茶。"
FLAT_TEXT_2 = "他看了看窗外，然后又坐了回去。"
FLAT_TEXT_3 = "他翻了翻桌上的文件，没什么特别的。"
GOTHIC_DARK_TEXT = "阴冷的雨滴打在墓碑上，乌鸦在枯树上嘶哑地叫着，死亡的气息弥漫在每一寸空气中。"
COMEDY_TEXT = "他一脚踩进水坑，溅了满身泥，路人哈哈大笑，他尴尬地挠了挠头，自己也笑了起来。"


@pytest.mark.unit
class TestEmotionalArcAnalyzer:
    """EmotionalArcAnalyzer 情感弧线分析器测试"""

    def setup_method(self):
        self.analyzer = EmotionalArcAnalyzer()

    def test_analyze_basic(self):
        """从故事文本中提取情感标签和强度"""
        result = self.analyzer.analyze(JOYFUL_TEXT)

        assert isinstance(result, EmotionalArcResult)
        assert hasattr(result, "valence")
        assert hasattr(result, "arousal")
        # 欢快文本 → 正向情感
        assert result.valence > 0.0
        assert 0.0 <= result.arousal <= 1.0

    def test_analyze_arc_tracking(self):
        """情感弧线追踪(joy→tension→catharsis等模式)"""
        history = [JOYFUL_TEXT, TENSE_TEXT, CATHARSIS_TEXT]
        arc = self.analyzer.analyze_arc(history)

        assert hasattr(arc, "pattern")
        assert arc.pattern is not None
        # 应识别出弧线中包含转折
        assert len(arc.pattern) >= 2

    def test_detect_flatline(self):
        """连续3段情感平坦时触发警告"""
        flat_history = [FLAT_TEXT_1, FLAT_TEXT_2, FLAT_TEXT_3]
        assert self.analyzer.detect_flatline(flat_history) is True

    def test_detect_no_flatline(self):
        """情感有波动时不触发"""
        varied_history = [JOYFUL_TEXT, TENSE_TEXT, CATHARSIS_TEXT]
        assert self.analyzer.detect_flatline(varied_history) is False

    def test_suggest_intervention_with_style(self):
        """基于风格配置生成节奏干预建议"""
        flat_history = [FLAT_TEXT_1, FLAT_TEXT_2, FLAT_TEXT_3]
        suggestion = self.analyzer.suggest_intervention(
            history=flat_history, style="gothic"
        )

        assert suggestion is not None
        assert isinstance(suggestion, str)
        assert len(suggestion) > 0

    def test_style_adaptation_gothic(self):
        """gothic允许持续低沉，不应触发flatline"""
        dark_history = [GOTHIC_DARK_TEXT, GOTHIC_DARK_TEXT, GOTHIC_DARK_TEXT]
        # gothic 风格下持续阴暗氛围是正常的
        assert self.analyzer.detect_flatline(dark_history, style="gothic") is False

    def test_style_adaptation_comedy(self):
        """comedy要求情感跳跃，平淡更容易触发"""
        mild_history = [FLAT_TEXT_1, FLAT_TEXT_2, FLAT_TEXT_3]
        # comedy 风格对平淡更敏感
        assert self.analyzer.detect_flatline(mild_history, style="comedy") is True

    def test_scene_classification(self):
        """场景功能分类：铺垫/发展/转折/高潮/收尾"""
        valid_categories = {"铺垫", "发展", "转折", "高潮", "收尾"}

        classification = self.analyzer.classify_scene(TENSE_TEXT)
        assert classification in valid_categories

        classification_joy = self.analyzer.classify_scene(JOYFUL_TEXT)
        assert classification_joy in valid_categories

    def test_degradation(self):
        """异常时优雅降级，不崩溃"""
        # 传入 None / 空字符串 / 非法类型都不应抛出异常
        result = self.analyzer.analyze("")
        assert isinstance(result, EmotionalArcResult)

        result_none = self.analyzer.analyze(None)
        assert isinstance(result_none, EmotionalArcResult)

        # detect_flatline 空列表不崩溃
        assert self.analyzer.detect_flatline([]) is False
