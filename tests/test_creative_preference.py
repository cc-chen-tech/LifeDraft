"""PreferenceLearner 偏好适配层 单元测试

L3 创意增强层 - 玩家偏好学习与适配
模块尚未实现，测试应为红色（TDD先行）
"""

import pytest

from src.ai.creative.preference_learner import (PlayerPreferences,
                                                PreferenceLearner)

# --------------- 测试数据 ---------------

ADVENTURE_HISTORY = [
    {"choice": "独自进入废弃矿洞", "type": "adventure", "week": 1},
    {"choice": "跳下悬崖追击敌人", "type": "adventure", "week": 2},
    {"choice": "徒手攀上城墙", "type": "adventure", "week": 3},
    {"choice": "闯入禁地寻宝", "type": "adventure", "week": 4},
    {"choice": "挑战武林盟主", "type": "adventure", "week": 5},
]

SOCIAL_HISTORY = [
    {"choice": "邀请村民共进晚餐", "type": "social", "week": 1},
    {"choice": "调解邻里纠纷", "type": "social", "week": 2},
    {"choice": "拜访老友叙旧", "type": "social", "week": 3},
    {"choice": "组织村民联防", "type": "social", "week": 4},
]

INVESTIGATION_HISTORY = [
    {"choice": "仔细检查密室墙壁", "type": "investigation", "week": 1},
    {"choice": "翻阅古籍查找线索", "type": "investigation", "week": 2},
    {"choice": "询问目击证人", "type": "investigation", "week": 3},
]

DECLINING_SCORES = [8.5, 7.2, 6.1, 5.0, 4.3]
STABLE_SCORES = [7.5, 7.8, 7.6, 7.4, 7.7]

MIXED_HISTORY_WITH_DECAY = [
    {"choice": "冒险行动A", "type": "adventure", "week": 1},
    {"choice": "社交行动B", "type": "social", "week": 5},
    {"choice": "冒险行动C", "type": "adventure", "week": 10},
    {"choice": "冒险行动D", "type": "adventure", "week": 14},
    {"choice": "调查行动E", "type": "investigation", "week": 15},
]


@pytest.mark.unit
class TestPreferenceLearner:
    """PreferenceLearner 偏好适配层测试"""

    def setup_method(self):
        self.learner = PreferenceLearner()

    def test_learn_from_history(self):
        """从决策历史提取隐性偏好信号"""
        prefs = self.learner.learn(decision_history=ADVENTURE_HISTORY)

        assert isinstance(prefs, PlayerPreferences)
        # 偏向冒险的历史 → 冒险倾向高
        assert hasattr(prefs, "adventure_tendency")
        assert prefs.adventure_tendency > 0.5

    def test_learn_preference_types(self):
        """识别不同类型偏好（调查型/社交型/冒险型）"""
        adventure_prefs = self.learner.learn(decision_history=ADVENTURE_HISTORY)
        social_prefs = self.learner.learn(decision_history=SOCIAL_HISTORY)
        investigation_prefs = self.learner.learn(decision_history=INVESTIGATION_HISTORY)

        # 各类型的主要偏好应不同
        assert adventure_prefs.primary_type == "adventure"
        assert social_prefs.primary_type == "social"
        assert investigation_prefs.primary_type == "investigation"

    def test_build_preference_hint(self):
        """生成偏好引导的Prompt片段(~50 tokens)"""
        prefs = self.learner.learn(decision_history=ADVENTURE_HISTORY)
        hint = self.learner.build_preference_hint(prefs)

        assert isinstance(hint, str)
        assert len(hint) > 0
        # 提示不应过长（约50 tokens ≈ 150字符以内）
        assert len(hint) <= 300

    def test_preference_hint_length(self):
        """提示长度不超过预算"""
        prefs = self.learner.learn(decision_history=SOCIAL_HISTORY)
        hint = self.learner.build_preference_hint(prefs, max_tokens=50)

        # 粗略估算：1 token ≈ 2-3个中文字符
        assert len(hint) <= 200

    def test_adjust_temperature_score_drop(self):
        """评分下降→温度临时+0.1~0.2"""
        base_temp = 0.7
        adjusted = self.learner.adjust_temperature(
            base_temperature=base_temp, recent_scores=DECLINING_SCORES
        )

        assert adjusted > base_temp
        assert adjusted <= base_temp + 0.3  # 不应调整过大

    def test_adjust_temperature_stable(self):
        """评分稳定→温度不变"""
        base_temp = 0.7
        adjusted = self.learner.adjust_temperature(
            base_temperature=base_temp, recent_scores=STABLE_SCORES
        )

        assert abs(adjusted - base_temp) < 0.05  # 基本不变

    def test_cold_start(self):
        """新用户（无历史）返回默认偏好"""
        prefs = self.learner.learn(decision_history=[])

        assert isinstance(prefs, PlayerPreferences)
        # 默认偏好应是均衡的
        assert (
            prefs.primary_type == "balanced"
            or prefs.adventure_tendency == pytest.approx(0.5, abs=0.2)
        )

    def test_preference_decay(self):
        """近期选择权重更高（衰减机制）"""
        prefs = self.learner.learn(decision_history=MIXED_HISTORY_WITH_DECAY)

        # 最近的选择（week 14, 15）是冒险+调查，早期的社交(week 5)权重应衰减
        # 因此冒险或调查倾向应高于社交
        assert prefs.adventure_tendency > 0.3 or prefs.primary_type != "social"

    def test_style_awareness(self):
        """在风格框架内微调而非覆盖风格规则"""
        prefs = self.learner.learn(decision_history=ADVENTURE_HISTORY)
        hint = self.learner.build_preference_hint(prefs, style="gothic")

        assert isinstance(hint, str)
        # 提示不应包含与gothic矛盾的内容（如"轻松愉快"）
        assert "轻松愉快" not in hint

    def test_degradation(self):
        """异常时优雅降级"""
        # None 输入不崩溃
        prefs = self.learner.learn(decision_history=None)
        assert isinstance(prefs, PlayerPreferences)

        # 畸形数据不崩溃
        prefs2 = self.learner.learn(decision_history=[{"bad": True}])
        assert isinstance(prefs2, PlayerPreferences)

        # 温度调整异常输入不崩溃
        adjusted = self.learner.adjust_temperature(
            base_temperature=0.7, recent_scores=None
        )
        assert isinstance(adjusted, float)
