"""FateEchoDatabase 宿命与回响 单元测试

L4 史诗叙事层 - 因果命题注册、触发检查与跨卷宗回响
模块尚未实现，测试应为红色（TDD先行）
"""

import pytest

from src.ai.narrative.fate_echo import FateEchoDatabase

# --------------- 测试数据 ---------------

PROPOSITION_KARMA = {
    "id": "karma_betrayal",
    "type": "因果报应",
    "cause": "主角在第3周背叛了盟友张三",
    "expected_effect": "张三在关键时刻反戈一击",
    "planted_week": 3,
    "trigger_conditions": {"min_week": 10, "requires_encounter": "张三"},
    "volume": 1,
}

PROPOSITION_DESTINY = {
    "id": "destiny_sword",
    "type": "天命应验",
    "cause": "算命先生预言'持剑者将改变天下'",
    "expected_effect": "主角在决战中觉醒神剑之力",
    "planted_week": 1,
    "trigger_conditions": {"min_week": 20, "requires_item": "断玉剑"},
    "volume": 1,
}

PROPOSITION_PROPHECY = {
    "id": "prophecy_fall",
    "type": "预言实现",
    "cause": "女巫预言'当双月齐明，王座将倾'",
    "expected_effect": "双月之夜，旧王朝覆灭",
    "planted_week": 2,
    "trigger_conditions": {"min_week": 15, "requires_event": "双月齐明"},
    "volume": 1,
}

PROPOSITION_CHOICE = {
    "id": "choice_consequence",
    "type": "选择后果",
    "cause": "主角选择放走了刺客",
    "expected_effect": "刺客日后成为暗中相助的力量",
    "planted_week": 5,
    "trigger_conditions": {"min_week": 12},
    "volume": 1,
}

CROSS_VOLUME_ECHO = {
    "id": "echo_ancient_seal",
    "type": "跨卷回响",
    "cause": "第一卷中打破的封印",
    "expected_effect": "封印碎片在第二卷引发连锁反应",
    "planted_week": 25,
    "trigger_conditions": {"min_week": 30, "volume": 2},
    "volume": 1,
}

EXPIRED_ECHO = {
    "id": "expired_rumor",
    "type": "因果报应",
    "cause": "散播的谣言",
    "expected_effect": "谣言反噬",
    "planted_week": 1,
    "trigger_conditions": {"min_week": 5, "max_week": 10},
    "volume": 1,
}


@pytest.mark.unit
class TestFateEchoDatabase:
    """FateEchoDatabase 宿命与回响数据库测试"""

    def setup_method(self):
        self.db = FateEchoDatabase()

    def test_register_proposition(self):
        """因果命题注册"""
        self.db.register(PROPOSITION_KARMA)
        self.db.register(PROPOSITION_DESTINY)

        all_props = self.db.get_all()
        assert len(all_props) == 2
        assert any(p["id"] == "karma_betrayal" for p in all_props)
        assert any(p["id"] == "destiny_sword" for p in all_props)

    def test_trigger_check(self):
        """触发条件检查"""
        self.db.register(PROPOSITION_KARMA)

        # 条件不满足（周数不够）
        context_early = {"current_week": 5, "encountered_characters": []}
        triggered = self.db.check_triggers(context_early)
        assert len(triggered) == 0

        # 条件满足
        context_ready = {"current_week": 12, "encountered_characters": ["张三"]}
        triggered = self.db.check_triggers(context_ready)
        assert len(triggered) == 1
        assert triggered[0]["id"] == "karma_betrayal"

    def test_cross_volume_echo(self):
        """跨卷宗回响强制编织"""
        self.db.register(CROSS_VOLUME_ECHO)

        # 在第二卷中检查
        context = {"current_week": 35, "current_volume": 2}
        echoes = self.db.check_triggers(context)

        assert len(echoes) >= 1
        assert echoes[0]["id"] == "echo_ancient_seal"

    def test_expired_echo_cleanup(self):
        """过期回响清理"""
        self.db.register(EXPIRED_ECHO)

        # 在过期之后清理
        self.db.cleanup_expired(current_week=15)

        remaining = self.db.get_all()
        # 过期的应被清理
        assert not any(p["id"] == "expired_rumor" for p in remaining)

    def test_style_chinese_classic(self):
        """中国古典=因果报应/天命应验"""
        self.db.register(PROPOSITION_KARMA)
        self.db.register(PROPOSITION_DESTINY)

        hint = self.db.generate_echo_hint(proposition_id="karma_betrayal", style="chinese_classic")

        assert isinstance(hint, str)
        assert len(hint) > 0

    def test_style_western(self):
        """西方=预言实现/选择后果"""
        self.db.register(PROPOSITION_PROPHECY)
        self.db.register(PROPOSITION_CHOICE)

        hint = self.db.generate_echo_hint(proposition_id="prophecy_fall", style="western")

        assert isinstance(hint, str)
        assert len(hint) > 0

    def test_get_pending_echoes(self):
        """获取当前待触发的回响列表"""
        self.db.register(PROPOSITION_KARMA)
        self.db.register(PROPOSITION_DESTINY)
        self.db.register(PROPOSITION_CHOICE)

        pending = self.db.get_pending_echoes(current_week=8)

        assert isinstance(pending, list)
        # 第8周时，所有命题都还未触发
        assert len(pending) == 3

        # 第25周时，有些命题可能已触发
        pending_later = self.db.get_pending_echoes(current_week=25)
        assert isinstance(pending_later, list)

    def test_degradation(self):
        """异常时优雅降级"""
        # 空数据库查询不崩溃
        triggered = self.db.check_triggers({"current_week": 10})
        assert isinstance(triggered, list)
        assert len(triggered) == 0

        # None 输入不崩溃
        self.db.register(None)
        assert isinstance(self.db.get_all(), list)

        # 清理空数据库不崩溃
        self.db.cleanup_expired(current_week=100)

        # 不存在的命题生成hint不崩溃
        hint = self.db.generate_echo_hint(proposition_id="nonexistent", style="chinese_classic")
        assert isinstance(hint, str)
