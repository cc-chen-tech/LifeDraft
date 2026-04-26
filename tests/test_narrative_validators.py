"""叙事验证器单元测试。"""

from src.ai.harness.narrative_validators import (
    validate_arc_hint_compliance, validate_conflict_directive_compliance,
    validate_pacing_variety, validate_three_act_structure,
    validate_world_event_integration)


def _make_long_text(
    base: str = "这是一段平凡的故事文本，描述着日常生活中的点点滴滴。",
    repeats: int = 40,
) -> str:
    """生成 > 500 字的长文本。"""
    return base * repeats


class TestThreeActStructure:
    """validate_three_act_structure 测试。"""

    def test_short_text_auto_pass(self):
        """短文本（<= 500 字）自动通过。"""
        text = "这是一段短故事。"
        passed, msg, details = validate_three_act_structure(text, {})
        assert passed is True
        assert msg == ""
        assert details["phases_count"] == 0

    def test_long_text_with_full_three_acts(self):
        """长文本有完整三幕（前段有"走进"、中段有"然而"、后段有"终于"）→ 通过。"""
        base = "这是一段普通的叙述文本用来填充字数。"
        # 构造 > 500 字文本，分四等分插入关键词
        chunk = base * 10  # ~180 字
        first = "走进了一座古老的城镇，" + chunk
        middle = chunk + "然而事情并非如此简单，" + chunk
        last = chunk + "终于迎来了结局。"
        text = first + middle + last
        assert len(text) > 500

        passed, msg, details = validate_three_act_structure(text, {})
        assert passed is True
        assert details["phases_count"] >= 2

    def test_long_text_no_act_keywords(self):
        """长文本无三幕关键词（纯平铺直叙）→ 失败。"""
        text = "今天天气很好，大家都很开心。" * 50
        assert len(text) > 500

        passed, msg, details = validate_three_act_structure(text, {})
        assert passed is False
        assert "三幕结构不完整" in msg
        assert details["phases_count"] < 2

    def test_long_text_only_one_phase(self):
        """长文本仅 1 个阶段 → 失败。"""
        # 只在前段放铺垫关键词，中段和后段无关键词
        base = "今天天气很好，大家都很开心。"
        chunk = base * 15
        text = "走进了一座城市，" + chunk + chunk + chunk
        assert len(text) > 500

        passed, msg, details = validate_three_act_structure(text, {})
        assert passed is False
        assert details["phases_count"] == 1


class TestPacingVariety:
    """validate_pacing_variety 测试。"""

    def test_no_pacing_intervention_auto_pass(self):
        """无 pacing_intervention hint → 自动通过。"""
        passed, msg, details = validate_pacing_variety("任意文本", {})
        assert passed is True

    def test_empty_pacing_intervention_auto_pass(self):
        """空字符串 pacing_intervention → 自动通过。"""
        context = {"narrative_hints": {"pacing_intervention": ""}}
        passed, msg, details = validate_pacing_variety("任意文本", context)
        assert passed is True

    def test_import_failure_auto_pass(self):
        """EmotionalArcAnalyzer 导入失败时自动通过。

        由于 EmotionalArcAnalyzer 可能不可用，测试导入失败路径。
        这里直接用 mock 模拟导入失败。
        """
        from unittest.mock import patch

        context = {"narrative_hints": {"pacing_intervention": "加快节奏"}}
        # 模拟 EmotionalArcAnalyzer 导入失败
        with patch.dict("sys.modules", {"src.ai.creative.emotional_arc": None}):
            passed, msg, details = validate_pacing_variety("一些文本", context)
            # 导入失败时应自动通过
            assert passed is True


class TestArcHintCompliance:
    """validate_arc_hint_compliance 测试。"""

    def test_no_arc_hint_auto_pass(self):
        """无 arc_hint → 自动通过。"""
        passed, msg, details = validate_arc_hint_compliance("任意文本", {})
        assert passed is True

    def test_arc_hint_struggle_with_matching_keywords(self):
        """arc_hint 包含"挣扎"，故事中有"矛盾"或"痛苦" → 通过。"""
        context = {"narrative_hints": {"arc_hint": "角色正处于挣扎阶段"}}
        text = "他内心充满了矛盾和痛苦，不知如何抉择。"
        passed, msg, details = validate_arc_hint_compliance(text, context)
        assert passed is True
        assert "挣扎" == details["detected_stage"]
        assert len(details["matched_keywords"]) > 0

    def test_arc_hint_turning_point_no_match(self):
        """arc_hint 包含"转折"，故事中无任何转折相关词 → 失败。"""
        context = {"narrative_hints": {"arc_hint": "这里应该有一个转折"}}
        text = "今天天气很好，大家都很开心，一切如常。"
        passed, msg, details = validate_arc_hint_compliance(text, context)
        assert passed is False
        assert "转折" in msg
        assert details["compliant"] is False

    def test_arc_hint_unknown_stage_auto_pass(self):
        """arc_hint 不包含任何已知阶段名 → 自动通过。"""
        context = {"narrative_hints": {"arc_hint": "请写得更精彩一些"}}
        text = "一段普通的故事文本。"
        passed, msg, details = validate_arc_hint_compliance(text, context)
        assert passed is True
        assert details.get("detected_stage") == ""


class TestWorldEventIntegration:
    """validate_world_event_integration 测试。"""

    def test_no_world_event_context_auto_pass(self):
        """无 world_event_context → 自动通过。"""
        passed, msg, details = validate_world_event_integration("任意文本", {})
        assert passed is True

    def test_world_event_keyword_found(self):
        """world_event_context 包含"经济危机"，故事中出现"经济危机" → 通过。"""
        context = {"narrative_hints": {"world_event_context": "经济危机"}}
        text = "在这个经济危机的年代，人们的生活发生了很大变化。"
        passed, msg, details = validate_world_event_integration(text, context)
        assert passed is True
        assert details["integrated"] is True
        assert len(details["found_in_story"]) > 0

    def test_world_event_keyword_not_found(self):
        """world_event_context 包含"战争爆发"，故事中完全无关 → 失败。"""
        context = {"narrative_hints": {"world_event_context": "战争爆发"}}
        text = "今天天气很好，小明去公园散步，看到了美丽的花朵。"
        passed, msg, details = validate_world_event_integration(text, context)
        assert passed is False
        assert "世界事件关键词未融入" in msg
        assert details["integrated"] is False


class TestConflictDirectiveCompliance:
    """validate_conflict_directive_compliance 测试。"""

    def test_no_conflict_directive_auto_pass(self):
        """无 conflict_directive → 自动通过。"""
        passed, msg, details = validate_conflict_directive_compliance("任意文本", {})
        assert passed is True

    def test_directive_with_conflict_content(self):
        """有 directive，故事中包含"冲突"或"矛盾" → 通过。"""
        context = {"narrative_hints": {"conflict_directive": "增加人际冲突"}}
        text = "两人之间的矛盾日益加深，冲突一触即发。"
        passed, msg, details = validate_conflict_directive_compliance(text, context)
        assert passed is True
        assert details["compliant"] is True
        assert len(details["found_in_story"]) > 0

    def test_directive_no_conflict_content(self):
        """有 directive，故事中完全无冲突内容 → 失败。"""
        context = {"narrative_hints": {"conflict_directive": "增加激烈对抗"}}
        text = "今天天气很好，小明和小红一起去公园散步，大家都很开心。"
        passed, msg, details = validate_conflict_directive_compliance(text, context)
        assert passed is False
        assert "冲突指令关键词未在故事中出现" in msg
        assert details["compliant"] is False
