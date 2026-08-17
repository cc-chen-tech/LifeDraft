"""QuickValidator Chinese Curly Quotes Contract Test

验证中文弯引号（“ ” ‘ ’）内的对话内容
不会被人称一致性检查误判为叙事人称错误。
Layer 3: 契约测试 — 弯引号处理行为约定。
"""

from src.ai.quick_validator import QuickValidator, quick_validate_story
import pytest

pytestmark = [pytest.mark.unit]



class TestQuickValidatorCurlyQuotesContract:
    """中文弯引号对话契约测试"""

    def test_curly_quotes_first_person_allowed(self):
        """弯引号内的「我」不应被误判为第一人称叙事"""
        validator = QuickValidator()
        story = "她微笑着说：“我今天很开心，我觉得很幸福。” 他点了点头。"
        result = validator.validate(story, language="zh")
        assert result.passed is True
        assert not any("第一人称" in issue for issue in result.issues)

    def test_curly_quotes_second_person_allowed(self):
        """弯引号内的「你」不应被误判为第二人称叙事"""
        validator = QuickValidator()
        story = "老师严厉地说：“你怎么又没做作业？” 学生低下了头。"
        result = validator.validate(story, language="zh")
        assert result.passed is True
        assert not any("第二人称" in issue for issue in result.issues)

    def test_mixed_quotes_all_allowed(self):
        """混合使用直引号和弯引号的对话都应被正确处理"""
        validator = QuickValidator()
        story = '他问："你好吗？" 她回答：“我很好，谢谢。”'
        result = validator.validate(story, language="zh")
        assert result.passed is True

    def test_single_curly_quotes_allowed(self):
        """单弯引号内的对话也应被正确处理"""
        validator = QuickValidator()
        story = "他心想：‘我一定要成功。’ 然后迈出了步伐。"
        result = validator.validate(story, language="zh")
        assert result.passed is True

    def test_outside_curly_quotes_still_detected(self):
        """弯引号外的人称仍应被检测"""
        validator = QuickValidator()
        story = "我今天去了公园。“天气真好。”"
        result = validator.validate(story, language="zh")
        assert result.passed is False
        assert any("第一人称" in issue for issue in result.issues)

    def test_convenience_function_with_curly_quotes(self):
        """quick_validate_story 便捷函数也应正确处理弯引号"""
        story = "他对她说：“你是我的唯一。” 然后转身离去。"
        result = quick_validate_story(story, language="zh")
        assert result.passed is True


class TestQuickValidatorCurlyQuotesEdgeCases:
    """弯引号边界情况测试"""

    def test_nested_curly_quotes(self):
        """嵌套弯引号应被正确处理"""
        validator = QuickValidator()
        story = "他引用道：“古人云：‘我生也有涯’，此乃真理。”"
        result = validator.validate(story, language="zh")
        assert result.passed is True

    def test_multiple_curly_quote_pairs(self):
        """多组弯引号应全部被过滤"""
        validator = QuickValidator()
        story = "“你来了？”他问。" "“我来了。”她答。" "“为什么？”" "“因为我想你。”"
        result = validator.validate(story, language="zh")
        assert result.passed is True

    def test_curly_quotes_with_punctuation(self):
        """弯引号与标点混用应正确过滤"""
        validator = QuickValidator()
        story = "他喊道：“你，给我站住！” 我愣在原地。"
        result = validator.validate(story, language="zh")
        # "我"在弯引号外（空格后），应被检测到
        assert result.passed is False
        assert any("第一人称" in issue for issue in result.issues)
