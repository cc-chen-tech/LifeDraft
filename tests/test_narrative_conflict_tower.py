"""ConflictTower 冲突升级塔 单元测试

L4 史诗叙事层 - 三级冲突池管理与主线引力算法
模块尚未实现，测试应为红色（TDD先行）
"""

import pytest

from src.ai.narrative.conflict_tower import ConflictTower

# --------------- 测试数据 ---------------

T1_CONFLICTS = [
    {
        "id": "t1_bandit",
        "tier": 1,
        "name": "山贼骚扰",
        "description": "小股山贼频频出没，骚扰来往商旅。",
    },
    {
        "id": "t1_debt",
        "tier": 1,
        "name": "债务纠纷",
        "description": "因意外欠下一笔不小的债务。",
    },
    {
        "id": "t1_rival",
        "tier": 1,
        "name": "同门之争",
        "description": "师兄弟之间为争夺传承暗中较量。",
    },
]

T2_CONFLICTS = [
    {
        "id": "t2_sect_war",
        "tier": 2,
        "name": "门派之争",
        "description": "两大门派因秘籍归属爆发冲突。",
    },
    {
        "id": "t2_conspiracy",
        "tier": 2,
        "name": "朝廷阴谋",
        "description": "有人暗中策划颠覆朝政。",
    },
]

T3_CONFLICTS = [
    {
        "id": "t3_demon_lord",
        "tier": 3,
        "name": "魔尊降世",
        "description": "封印千年的魔尊即将破封而出，天下大乱。",
    },
]

MAIN_STORYLINE = {
    "id": "main_quest",
    "name": "寻找上古神器",
    "description": "传说中能封印魔尊的上古神器散落四方。",
    "milestones": ["获取线索", "找到第一件", "集齐神器", "最终封印"],
}


@pytest.mark.unit
class TestConflictTower:
    """ConflictTower 冲突升级塔测试"""

    def setup_method(self):
        self.tower = ConflictTower()

    def test_three_tier_management(self):
        """T1/T2/T3三级池管理"""
        for c in T1_CONFLICTS:
            self.tower.add_conflict(c)
        for c in T2_CONFLICTS:
            self.tower.add_conflict(c)
        for c in T3_CONFLICTS:
            self.tower.add_conflict(c)

        assert len(self.tower.get_tier(1)) == 3
        assert len(self.tower.get_tier(2)) == 2
        assert len(self.tower.get_tier(3)) == 1

    def test_conflict_escalation(self):
        """冲突升级判定（连续N周T1→解锁T2）"""
        for c in T1_CONFLICTS:
            self.tower.add_conflict(c)
        for c in T2_CONFLICTS:
            self.tower.add_conflict(c)

        # 模拟连续多周T1冲突活跃
        for week in range(1, 6):
            self.tower.record_weekly_activity(
                week=week, active_conflicts=["t1_bandit", "t1_rival"]
            )

        # 连续活跃后应触发T2解锁
        unlocked = self.tower.check_escalation()
        assert len(unlocked) > 0
        assert any(c["tier"] == 2 for c in unlocked)

    def test_main_gravity(self):
        """主线引力算法：偏离度计算"""
        self.tower.set_main_storyline(MAIN_STORYLINE)

        # 玩家当前状态
        player_progress = {
            "current_focus": "处理债务纠纷",  # 偏离主线
            "main_quest_milestone": "获取线索",
        }

        deviation = self.tower.compute_deviation(player_progress)

        assert isinstance(deviation, float)
        assert 0.0 <= deviation <= 1.0
        # 处理债务纠纷偏离了主线 → 偏离度较高
        assert deviation > 0.3

    def test_boss_battle_trigger(self):
        """阶段性Boss战触发条件"""
        for c in T1_CONFLICTS + T2_CONFLICTS + T3_CONFLICTS:
            self.tower.add_conflict(c)
        self.tower.set_main_storyline(MAIN_STORYLINE)

        # 模拟推进到一个里程碑节点
        trigger = self.tower.check_boss_trigger(
            current_week=20,
            milestone="集齐神器",
            tier_2_resolved=2,
        )

        assert isinstance(trigger, dict) or trigger is not None
        if trigger:
            assert "conflict_id" in trigger or "boss" in trigger

    def test_style_chinese_classic(self):
        """中国古典=劫难递增/章回Boss"""
        tower = ConflictTower(style="chinese_classic")
        for c in T1_CONFLICTS:
            tower.add_conflict(c)

        tier_config = tower.get_tier_config()
        assert tier_config is not None
        # 中国古典风格的命名或配置
        assert tier_config.get("style") == "chinese_classic" or "劫难" in str(
            tier_config
        )

    def test_style_western(self):
        """西方=学年大考/终极对决"""
        tower = ConflictTower(style="western")
        tier_config = tower.get_tier_config()
        assert tier_config is not None
        assert tier_config.get("style") == "western" or "对决" in str(tier_config)

    def test_degradation(self):
        """异常时优雅降级"""
        # 空塔查询不崩溃
        assert self.tower.get_tier(1) == []
        assert self.tower.get_tier(99) == []

        # 无主线时计算偏离度不崩溃
        deviation = self.tower.compute_deviation({})
        assert isinstance(deviation, float)

        # None 输入不崩溃
        self.tower.add_conflict(None)
        result = self.tower.check_escalation()
        assert isinstance(result, list)
