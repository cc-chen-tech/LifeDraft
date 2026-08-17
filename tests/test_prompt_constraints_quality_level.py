"""Prompt 约束三级强度测试."""

from config.prompts._helpers import _build_common_story_constraints
import pytest

pytestmark = [pytest.mark.unit]



def test_fast_constraints_are_minimal():
    """FAST 模式约束应更简短."""
    text = _build_common_story_constraints("zh", quality_level="fast")
    assert "第三人称" in text
    assert "极简" in text or "快速" in text or len(text) < 500


def test_expert_constraints_are_standard():
    """EXPERT 模式约束为标准长度."""
    text = _build_common_story_constraints("zh", quality_level="expert")
    assert "第三人称" in text
    assert "禁止跳脱叙事" in text
    assert "禁止编造过往事件" in text


def test_master_constraints_are_strict():
    """MASTER 模式约束应更严格详细."""
    text = _build_common_story_constraints("zh", quality_level="master")
    assert "第三人称" in text
    assert "大师" in text or "文学编辑" in text or "严格" in text


def test_english_constraints_also_support_levels():
    """英文约束也支持三级."""
    fast_en = _build_common_story_constraints("en", quality_level="fast")
    master_en = _build_common_story_constraints("en", quality_level="master")
    assert "third-person" in fast_en.lower() or "perspective" in fast_en.lower()
    assert "third-person" in master_en.lower() or "perspective" in master_en.lower()
    assert len(master_en) >= len(fast_en)
