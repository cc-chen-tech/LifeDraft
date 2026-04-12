"""CharacterArcEngine 人物弧光追踪 单元测试

L4 史诗叙事层 - 角色弧光5阶段追踪与约束生成
模块尚未实现，测试应为红色（TDD先行）
"""

import pytest

from src.ai.narrative.character_arc import CharacterArcEngine


# --------------- 测试数据 ---------------

SAMPLE_CHARACTER = {
    "name": "林逸风",
    "initial_flaw": "自负轻狂",
    "desire": "成为天下第一剑客",
    "backstory": "出身名门，自幼天赋异禀，却因骄傲失去了最重要的人。",
}

SAMPLE_CHARACTER_WESTERN = {
    "name": "Elara",
    "initial_flaw": "恐惧失败",
    "desire": "拯救被诅咒的王国",
    "backstory": "平凡的牧羊女，在一次偶然中发现自己拥有古老的力量。",
}

SAMPLE_CHARACTER_JAPANESE = {
    "name": "花散里",
    "initial_flaw": "执念过深",
    "desire": "找回失散的妹妹",
    "backstory": "大火之后独自存活的少女，背负着幸存者的罪恶感。",
}

ARC_EVENTS = [
    {"week": 1, "event": "在比武中轻松获胜", "phase": "稳态"},
    {"week": 3, "event": "挚友因自己的疏忽而受重伤", "phase": "触发"},
    {"week": 6, "event": "独自修行却屡遭失败", "phase": "挣扎"},
    {"week": 10, "event": "放下执念，领悟剑道真意", "phase": "转折"},
    {"week": 15, "event": "以全新的姿态面对旧敌", "phase": "新稳态"},
]


@pytest.mark.unit
class TestCharacterArcEngine:
    """CharacterArcEngine 人物弧光追踪测试"""

    def setup_method(self):
        self.engine = CharacterArcEngine()

    def test_five_stage_arc(self):
        """5阶段弧光定义（稳态→触发→挣扎→转折→新稳态）"""
        arc = self.engine.create_arc(SAMPLE_CHARACTER)

        assert hasattr(arc, "phases")
        expected_phases = ["稳态", "触发", "挣扎", "转折", "新稳态"]
        assert len(arc.phases) == 5
        for phase_name in expected_phases:
            assert any(p.name == phase_name for p in arc.phases)

    def test_phase_progression(self):
        """阶段推进判定逻辑"""
        arc = self.engine.create_arc(SAMPLE_CHARACTER)

        # 初始阶段应为"稳态"
        assert arc.current_phase.name == "稳态"

        # 触发事件后推进到下一阶段
        trigger_event = {"event": "挚友受重伤", "intensity": 0.8}
        self.engine.process_event(arc, trigger_event)
        assert arc.current_phase.name == "触发"

    def test_personality_shift(self):
        """性格维度微小偏移生成"""
        arc = self.engine.create_arc(SAMPLE_CHARACTER)
        trigger_event = {"event": "挚友受重伤", "intensity": 0.8}

        shift = self.engine.compute_personality_shift(arc, trigger_event)

        assert isinstance(shift, dict)
        # 偏移幅度应在合理范围
        for dimension, delta in shift.items():
            assert isinstance(dimension, str)
            assert -0.3 <= delta <= 0.3  # 微小偏移

    def test_style_chinese_classic(self):
        """中国古典=天命觉醒弧"""
        arc = self.engine.create_arc(SAMPLE_CHARACTER, style="chinese_classic")

        assert arc.arc_type in ("天命觉醒", "chinese_classic")
        # 中国古典弧应包含特定阶段名
        phase_names = [p.name for p in arc.phases]
        assert len(phase_names) == 5

    def test_style_western(self):
        """西方=英雄之旅弧"""
        arc = self.engine.create_arc(SAMPLE_CHARACTER_WESTERN, style="western")

        assert arc.arc_type in ("英雄之旅", "western")

    def test_style_japanese(self):
        """日本=无常接受弧"""
        arc = self.engine.create_arc(SAMPLE_CHARACTER_JAPANESE, style="japanese")

        assert arc.arc_type in ("无常接受", "japanese")

    def test_arc_constraint_generation(self):
        """生成弧光进度约束注入Prompt"""
        arc = self.engine.create_arc(SAMPLE_CHARACTER)
        constraint = self.engine.generate_constraint(arc)

        assert isinstance(constraint, str)
        assert len(constraint) > 0
        # 约束应提及当前阶段或角色名
        assert "林逸风" in constraint or arc.current_phase.name in constraint

    def test_initial_setup(self):
        """定义角色初始缺陷/欲望→预设终点"""
        arc = self.engine.create_arc(SAMPLE_CHARACTER)

        assert arc.initial_flaw == "自负轻狂"
        assert arc.desire == "成为天下第一剑客"
        # 应有预设终点
        assert hasattr(arc, "endpoint") or hasattr(arc, "resolution")

    def test_degradation(self):
        """异常时优雅降级"""
        # 空角色数据不崩溃
        arc = self.engine.create_arc({})
        assert arc is not None

        # None 输入不崩溃
        arc2 = self.engine.create_arc(None)
        assert arc2 is not None

        # 约束生成对异常弧不崩溃
        constraint = self.engine.generate_constraint(None)
        assert isinstance(constraint, str)
