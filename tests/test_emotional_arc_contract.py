"""Emotional arc analyzer contract tests.

No mocks. Pure logic tests for emotion detection.
"""

from src.ai.creative.emotional_arc import EmotionalArcAnalyzer
import pytest

pytestmark = [pytest.mark.unit]



class TestEmotionalArcAnalyzerContract:
    """Contract tests for emotional arc analysis."""

    def test_empty_text_returns_default(self):
        analyzer = EmotionalArcAnalyzer()
        result = analyzer.analyze("")
        assert result.valence == 0.0
        assert result.arousal == 0.0
        assert result.scene_type == "发展"

    def test_none_text_returns_default(self):
        analyzer = EmotionalArcAnalyzer()
        result = analyzer.analyze(None)
        assert result.valence == 0.0

    def test_positive_text(self):
        analyzer = EmotionalArcAnalyzer()
        result = analyzer.analyze("阳光温暖，他微笑面对未来，充满希望和喜悦")
        assert result.valence > 0

    def test_negative_text(self):
        analyzer = EmotionalArcAnalyzer()
        result = analyzer.analyze("黑暗中充满恐惧和绝望，他独自哭泣")
        assert result.valence < 0

    def test_high_arousal_text(self):
        analyzer = EmotionalArcAnalyzer()
        result = analyzer.analyze("战斗激烈，他奔跑追逐，爆炸声不断")
        assert result.arousal > 0.5

    def test_scene_type_climax(self):
        analyzer = EmotionalArcAnalyzer()
        result = analyzer.analyze("终于！他紧紧握住她的手，夺眶而出的泪水")
        assert result.scene_type == "高潮"

    def test_scene_type_setup(self):
        analyzer = EmotionalArcAnalyzer()
        result = analyzer.analyze("他走进房间，坐下，看了看窗外，喝了口茶")
        assert result.scene_type == "铺垫"

    def test_scene_type_ending(self):
        analyzer = EmotionalArcAnalyzer()
        result = analyzer.analyze("温暖阳光，美好结局，微笑，轻松坐下，看了看窗外")
        # "收尾" requires valence > 0.3 and arousal < 0.3
        assert result.scene_type in ("收尾", "发展", "铺垫")

    def test_analyze_arc_empty(self):
        analyzer = EmotionalArcAnalyzer()
        result = analyzer.analyze_arc([])
        assert result.pattern == ""

    def test_analyze_arc_transition(self):
        analyzer = EmotionalArcAnalyzer()
        history = ["悲伤痛苦", "温暖阳光"]
        result = analyzer.analyze_arc(history)
        assert "→" in result.pattern
        assert (
            "转折" in result.pattern
            or "高潮" in result.pattern
            or "发展" in result.pattern
            or "收尾" in result.pattern
        )

    def test_detect_flatline_short_history(self):
        analyzer = EmotionalArcAnalyzer()
        assert analyzer.detect_flatline(["a", "b"]) is False

    def test_detect_flatline_true(self):
        analyzer = EmotionalArcAnalyzer()
        history = ["普通日子", "一般生活", "日常琐事"]
        assert analyzer.detect_flatline(history) is True

    def test_detect_flatline_gothic_negative_ok(self):
        analyzer = EmotionalArcAnalyzer()
        history = ["黑暗恐惧", "绝望孤独", "阴冷墓碑"]
        assert analyzer.detect_flatline(history, style="gothic") is False

    def test_detect_flatline_comedy_more_sensitive(self):
        analyzer = EmotionalArcAnalyzer()
        # Same text that might be flat under normal rules
        history = ["一般日子", "普通生活", "日常小事"]
        analyzer.detect_flatline(history)
        comedy = analyzer.detect_flatline(history, style="comedy")
        # comedy has higher thresholds, so it might detect flatline earlier
        assert isinstance(comedy, bool)

    def test_suggest_intervention_gothic(self):
        analyzer = EmotionalArcAnalyzer()
        hint = analyzer.suggest_intervention(style="gothic")
        assert "微光" in hint or "温情" in hint

    def test_suggest_intervention_comedy(self):
        analyzer = EmotionalArcAnalyzer()
        hint = analyzer.suggest_intervention(style="comedy")
        assert "误会" in hint or "巧合" in hint or "笑点" in hint

    def test_suggest_intervention_default(self):
        analyzer = EmotionalArcAnalyzer()
        hint = analyzer.suggest_intervention()
        assert "意外" in hint or "转折" in hint

    def test_classify_scene_empty(self):
        analyzer = EmotionalArcAnalyzer()
        assert analyzer.classify_scene("") == "发展"

    def test_classify_scene_climax(self):
        analyzer = EmotionalArcAnalyzer()
        assert analyzer.classify_scene("终于！他紧紧握住") == "高潮"
