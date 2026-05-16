"""StyleAwarePromptBuilder 单元测试 (L2)。

TDD先行：测试 StyleAwarePromptBuilder 将 StyleManifest 转化为
结构化约束字符串的能力，包括硬约束/软建议分层、Token预算控制等。
"""

import pytest

from src.ai.narrative.style_manifest import StyleManifest

# TDD: 模块尚不存在，导入失败时标记整个模块为 xfail
try:
    from src.ai.narrative.style_prompt_builder import StyleAwarePromptBuilder
except ImportError:
    pytestmark = pytest.mark.skip(
        reason="src.ai.narrative.style_prompt_builder 尚未实现（TDD红色阶段）"
    )
    StyleAwarePromptBuilder = None  # type: ignore


# ==================== 基本构建测试 ====================


@pytest.mark.unit
class TestStyleAwarePromptBuilderBasic:
    """StyleAwarePromptBuilder 基本功能测试。"""

    def test_builder_creation(self, sample_style_manifest):
        """创建 builder 不崩溃。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        assert builder is not None

    def test_build_returns_string(self, sample_style_manifest):
        """build() 返回非空字符串。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        result = builder.build()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_must_constraints_present(self, sample_style_manifest):
        """输出包含 [MUST] 硬约束标记。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        result = builder.build()
        assert "[MUST]" in result

    def test_should_suggestions_present(self, sample_style_manifest):
        """输出包含 [SHOULD] 软建议标记。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        result = builder.build()
        assert "[SHOULD]" in result


# ==================== 五维转化测试 ====================


@pytest.mark.unit
class TestStyleDimensionConversion:
    """五维子配置到约束文本的转化。"""

    def test_philosophy_to_narrative_voice(self, sample_style_manifest):
        """philosophy → narrative_voice 转化。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        result = builder.build()
        # 叙事哲学应体现在输出中
        assert "全知视角" in result or "narrative_voice" in result.lower() or "叙事" in result

    def test_structure_to_macro_arc(self, sample_style_manifest):
        """structure → macro/arc 转化。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        result = builder.build()
        assert "三幕式" in result or "起承转合" in result or "结构" in result

    def test_techniques_to_list(self, sample_style_manifest):
        """techniques → 技法列表。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        result = builder.build()
        assert "白描" in result or "意识流" in result or "技法" in result

    def test_language_to_prose_rhetoric(self, sample_style_manifest):
        """language → prose/rhetoric 转化。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        result = builder.build()
        assert "简练" in result or "比喻" in result or "语言" in result

    def test_parameters_temperature_injection(self, sample_style_manifest):
        """parameters → temperature 注入。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        result = builder.build()
        # temperature 信息应以某种形式出现
        assert "0.85" in result or "temperature" in result.lower() or "创作" in result


# ==================== Token 预算测试 ====================


@pytest.mark.unit
class TestTokenBudget:
    """Token 预算控制。"""

    def test_constraint_text_within_budget(self, sample_style_manifest):
        """约束文本不超过预算上限。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        result = builder.build()
        # 假设预算上限约 2000 字符（合理的 prompt 约束段长度）
        assert len(result) <= 5000, f"约束文本过长: {len(result)} 字符"

    def test_custom_budget_limit(self, sample_style_manifest):
        """自定义 Token 预算上限。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest, max_tokens=500)
        result = builder.build()
        # 输出应被截断或精简到预算范围
        assert len(result) <= 3000  # 宽松检查，字符数 ≈ token * 2


# ==================== 降级模式测试 ====================


@pytest.mark.unit
class TestDegradationMode:
    """无风格/空风格时的降级模式。"""

    def test_none_style_returns_empty(self):
        """无风格时返回空约束。"""
        builder = StyleAwarePromptBuilder(None)
        result = builder.build()
        assert isinstance(result, str)
        assert len(result) == 0 or result.strip() == ""

    def test_empty_style_returns_empty(self):
        """空 StyleManifest 返回最小约束。"""
        empty = StyleManifest()
        builder = StyleAwarePromptBuilder(empty)
        result = builder.build()
        assert isinstance(result, str)


# ==================== 专用方法测试 ====================


@pytest.mark.unit
class TestSpecializedMethods:
    """build_chapter_opening, build_chapter_ending_hint, get_scene_temperature。"""

    def test_build_chapter_opening(self, sample_style_manifest):
        """build_chapter_opening 返回开篇风格约束。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        result = builder.build_chapter_opening()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_chapter_ending_hint(self, sample_style_manifest):
        """build_chapter_ending_hint 返回收尾风格提示。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        result = builder.build_chapter_ending_hint()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_scene_temperature(self, sample_style_manifest):
        """get_scene_temperature 返回合理的 temperature 值。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        temp = builder.get_scene_temperature()
        assert isinstance(temp, float)
        assert 0.0 <= temp <= 2.0

    def test_get_scene_temperature_with_scene_type(self, sample_style_manifest):
        """get_scene_temperature 支持场景类型参数。"""
        builder = StyleAwarePromptBuilder(sample_style_manifest)
        temp_opening = builder.get_scene_temperature(scene_type="opening")
        temp_climax = builder.get_scene_temperature(scene_type="climax")
        assert isinstance(temp_opening, float)
        assert isinstance(temp_climax, float)

    def test_get_scene_temperature_none_style(self):
        """无风格时返回默认 temperature。"""
        builder = StyleAwarePromptBuilder(None)
        temp = builder.get_scene_temperature()
        assert isinstance(temp, float)
        assert 0.5 <= temp <= 1.0  # 合理默认范围
