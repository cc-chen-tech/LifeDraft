"""ForeshadowingTechniqueLibrary + HookInjector 单元测试

L3 创意增强层 - 伏笔技法库与钩子注入
模块尚未实现，测试应为红色（TDD先行）
"""

import pytest

from src.ai.creative.foreshadowing_tech import (
    ForeshadowingTechniqueLibrary,
    HookInjector,
    RecoveryTechnique,
)


# --------------- 测试数据 ---------------

FORESHADOWING_ITEM = {
    "type": "item",
    "name": "断玉簪",
    "description": "母亲留下的半截玉簪，断口处隐约有血痕。",
    "planted_week": 3,
}

FORESHADOWING_DIALOGUE = {
    "type": "dialogue",
    "name": "掌柜密语",
    "description": "客栈掌柜低声说：'三日后，城东会有大事。'",
    "planted_week": 5,
}

FORESHADOWING_CHARACTER = {
    "type": "character",
    "name": "少年剑客",
    "description": "总在关键时刻出现又消失的神秘少年，左手始终藏在袖中。",
    "planted_week": 2,
}

FORESHADOWING_EVENT = {
    "type": "event",
    "name": "井水变红",
    "description": "村口的井水在满月之夜变成了淡红色。",
    "planted_week": 1,
}

OVERDUE_FORESHADOWING = {
    "type": "item",
    "name": "锈铁令牌",
    "description": "从密室中找到的铁令牌，刻着不明文字。",
    "planted_week": 1,
    "current_week": 20,
    "recovery_deadline": 15,
}

SAMPLE_OPTIONS = [
    {"text": "走进密林深处", "effects": {"mood": -5}},
    {"text": "沿着河流前行", "effects": {"energy": -10}},
    {"text": "返回村庄休息", "effects": {"energy": 10}},
]


@pytest.mark.unit
class TestForeshadowingTechniqueLibrary:
    """ForeshadowingTechniqueLibrary 伏笔技法库测试"""

    def setup_method(self):
        self.library = ForeshadowingTechniqueLibrary()

    def test_match_technique_item(self):
        """物品类伏笔→功能反转技巧"""
        technique = self.library.match_technique(FORESHADOWING_ITEM)

        assert isinstance(technique, RecoveryTechnique)
        assert "反转" in technique.name or "功能" in technique.name

    def test_match_technique_dialogue(self):
        """对话类伏笔→弦外之音技巧"""
        technique = self.library.match_technique(FORESHADOWING_DIALOGUE)

        assert isinstance(technique, RecoveryTechnique)
        assert "弦外之音" in technique.name or "对话" in technique.name

    def test_match_technique_character(self):
        """人物类伏笔→成长映照技巧"""
        technique = self.library.match_technique(FORESHADOWING_CHARACTER)

        assert isinstance(technique, RecoveryTechnique)
        assert "映照" in technique.name or "成长" in technique.name or "人物" in technique.name

    def test_match_technique_event(self):
        """事件类伏笔→因果延迟技巧"""
        technique = self.library.match_technique(FORESHADOWING_EVENT)

        assert isinstance(technique, RecoveryTechnique)
        assert "因果" in technique.name or "延迟" in technique.name or "事件" in technique.name

    def test_style_aware_recovery_chinese_classic(self):
        """中国古典风格=草蛇灰线式回收"""
        technique = self.library.get_style_recovery(
            foreshadowing=FORESHADOWING_ITEM, style="chinese_classic"
        )

        assert isinstance(technique, RecoveryTechnique)
        assert "草蛇灰线" in technique.name or "chinese_classic" in technique.style

    def test_style_aware_recovery_western(self):
        """西方风格=麦格芬揭露式"""
        technique = self.library.get_style_recovery(
            foreshadowing=FORESHADOWING_ITEM, style="western"
        )

        assert isinstance(technique, RecoveryTechnique)
        assert "麦格芬" in technique.name or "western" in technique.style

    def test_style_aware_recovery_honkaku(self):
        """本格推理=线索伏笔"""
        technique = self.library.get_style_recovery(
            foreshadowing=FORESHADOWING_ITEM, style="honkaku"
        )

        assert isinstance(technique, RecoveryTechnique)
        assert "线索" in technique.name or "honkaku" in technique.style

    def test_build_recovery_hint(self):
        """生成伏笔回收的Prompt提示"""
        hint = self.library.build_recovery_hint(
            foreshadowing=FORESHADOWING_ITEM, style="chinese_classic"
        )

        assert isinstance(hint, str)
        assert len(hint) > 0
        # 提示应包含伏笔相关信息
        assert "断玉簪" in hint or "玉簪" in hint

    def test_overdue_foreshadowing_reminder(self):
        """超过N周未回收的伏笔提醒"""
        reminders = self.library.check_overdue(
            foreshadowings=[OVERDUE_FORESHADOWING], current_week=20
        )

        assert len(reminders) > 0
        assert "锈铁令牌" in reminders[0] or OVERDUE_FORESHADOWING["name"] in str(
            reminders
        )


@pytest.mark.unit
class TestHookInjector:
    """HookInjector 钩子注入器测试"""

    def setup_method(self):
        self.injector = HookInjector()

    def test_inject_hooks(self):
        """在选项中植入信息缺口钩子"""
        enhanced_options = self.injector.inject_hooks(
            options=SAMPLE_OPTIONS,
            context="密林中传来若隐若现的歌声",
        )

        assert len(enhanced_options) >= len(SAMPLE_OPTIONS)
        # 至少有一个选项被增强或新增了钩子
        has_hook = any(
            opt.get("hook") or opt.get("curiosity_gap")
            for opt in enhanced_options
        )
        assert has_hook

    def test_inject_hooks_empty_options(self):
        """空选项列表不崩溃"""
        result = self.injector.inject_hooks(options=[], context="任意上下文")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_degradation(self):
        """异常时优雅降级"""
        # None输入不崩溃
        result = self.injector.inject_hooks(options=None, context=None)
        assert isinstance(result, list)

        # 畸形选项不崩溃
        result2 = self.injector.inject_hooks(
            options=[{"bad_key": 123}], context=""
        )
        assert isinstance(result2, list)
