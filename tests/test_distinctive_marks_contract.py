"""Distinctive marks prominence contract tests.
import pytest

pytestmark = [pytest.mark.unit]


验证外貌锚点中的 distinctive_marks 在 prompt 中获得足够高的优先级和可见性。
"""


class TestDistinctiveMarksProminence:
    """测试标志性识别特征在 prompt 中的优先级"""

    def test_build_prompt_segment_includes_distinctive_marks(self):
        """build_prompt_segment 必须包含 distinctive_marks"""
        from src.services.image.appearance_anchor import \
            CharacterAppearanceAnchor

        anchor = CharacterAppearanceAnchor(
            name="测试人物",
            distinctive_marks=["蓝紫色渐变发色", "左眉闪电形剃痕"],
        )
        segment = anchor.build_prompt_segment()

        assert (
            "蓝紫色渐变发色" in segment
        ), f"prompt 片段必须包含 distinctive_marks，实际: {segment}"
        assert (
            "左眉闪电形剃痕" in segment
        ), f"prompt 片段必须包含 distinctive_marks，实际: {segment}"

    def test_distinctive_marks_has_high_priority_label(self):
        """distinctive_marks 必须使用高优先级标签"""
        from src.services.image.appearance_anchor import \
            CharacterAppearanceAnchor

        anchor = CharacterAppearanceAnchor(
            name="测试人物",
            distinctive_marks=["左脸颊有一道伤疤"],
        )
        segment = anchor.build_prompt_segment()

        assert "最高优先级" in segment, f"distinctive_marks 必须有'最高优先级'标签，实际: {segment}"
        assert (
            "绝对不可丢失" in segment
        ), f"distinctive_marks 必须有'绝对不可丢失'标签，实际: {segment}"

    def test_distinctive_marks_explains_importance(self):
        """distinctive_marks 必须解释其重要性（区分不同人物的关键标识）"""
        from src.services.image.appearance_anchor import \
            CharacterAppearanceAnchor

        anchor = CharacterAppearanceAnchor(
            name="测试人物",
            distinctive_marks=["佩戴银色细框眼镜"],
        )
        segment = anchor.build_prompt_segment()

        assert (
            "区别于其他人的关键标识" in segment
        ), f"distinctive_marks 必须说明其区分作用，实际: {segment}"
        assert (
            "必须在所有图片中清晰可见" in segment
        ), f"distinctive_marks 必须要求清晰可见，实际: {segment}"

    def test_build_scene_prompt_emphasizes_distinctive_marks(self):
        """build_scene_prompt 必须强调 distinctive_marks 在场景中的可见性"""
        from src.services.image.appearance_anchor import \
            CharacterAppearanceAnchor

        anchor = CharacterAppearanceAnchor(
            name="测试人物",
            distinctive_marks=["右手腕佩戴红绳", "右耳三个耳钉"],
        )
        prompt = anchor.build_scene_prompt()

        assert "标志性识别特征" in prompt, f"场景 prompt 必须包含'标志性识别特征'，实际: {prompt}"
        assert (
            "场景中必须清晰可见" in prompt
        ), f"场景 prompt 必须要求'场景中必须清晰可见'，实际: {prompt}"
        assert "右手腕佩戴红绳" in prompt, f"场景 prompt 必须包含具体特征，实际: {prompt}"

    def test_empty_distinctive_marks_omitted(self):
        """没有 distinctive_marks 时不应生成相关段落"""
        from src.services.image.appearance_anchor import \
            CharacterAppearanceAnchor

        anchor = CharacterAppearanceAnchor(
            name="测试人物",
            distinctive_marks=[],
        )
        segment = anchor.build_prompt_segment()

        assert (
            "标志性识别特征" not in segment
        ), f"空 distinctive_marks 不应生成段落，实际: {segment}"

    def test_multiple_distinctive_marks_joined(self):
        """多个 distinctive_marks 应使用顿号连接"""
        from src.services.image.appearance_anchor import \
            CharacterAppearanceAnchor

        anchor = CharacterAppearanceAnchor(
            name="测试人物",
            distinctive_marks=["特征A", "特征B", "特征C"],
        )
        segment = anchor.build_prompt_segment()

        assert "特征A、特征B、特征C" in segment, f"多个特征应使用顿号连接，实际: {segment}"
