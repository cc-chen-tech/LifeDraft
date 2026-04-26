"""WorldBreathingEngine 世界呼吸与流言 单元测试

L4 史诗叙事层 - 世界背景事件自动推进与信息渗透
模块尚未实现，测试应为红色（TDD先行）
"""

import pytest

from src.ai.narrative.world_breathing import WorldBreathingEngine

# --------------- 测试数据 ---------------

SAMPLE_EVENTS = [
    {
        "id": "season_autumn",
        "type": "季节变化",
        "name": "秋风渐起",
        "description": "枫叶染红了整座山谷，早晚已有寒意。",
        "trigger_week": 8,
    },
    {
        "id": "market_crisis",
        "type": "市场波动",
        "name": "盐价飞涨",
        "description": "西域商路被截断，盐铁价格一夜翻倍。",
        "trigger_week": 10,
    },
    {
        "id": "political_unrest",
        "type": "政治动荡",
        "name": "太子遇刺",
        "description": "京城传来太子遇刺的消息，朝野震动。",
        "trigger_week": 12,
    },
    {
        "id": "natural_disaster",
        "type": "自然灾害",
        "name": "洪水泛滥",
        "description": "连日暴雨导致黄河决堤，数万灾民流离失所。",
        "trigger_week": 15,
    },
    {
        "id": "rumor_spread",
        "type": "流言传播",
        "name": "江湖传闻",
        "description": "有人在北疆见到了消失十年的剑圣。",
        "trigger_week": 6,
    },
]

WESTERN_EVENTS = [
    {
        "id": "prophecy",
        "type": "预言",
        "name": "星辰之语",
        "description": "占星师在月食之夜看到了末日的征兆。",
        "trigger_week": 5,
    },
    {
        "id": "traveler_tale",
        "type": "旅人传说",
        "name": "龙之传闻",
        "description": "从东方来的旅人声称在群山之中看到了飞龙的身影。",
        "trigger_week": 7,
    },
]


@pytest.mark.unit
class TestWorldBreathingEngine:
    """WorldBreathingEngine 世界呼吸引擎测试"""

    def setup_method(self):
        self.engine = WorldBreathingEngine()

    def test_event_calendar(self):
        """事件日历注册与推进"""
        for event in SAMPLE_EVENTS:
            self.engine.register_event(event)

        calendar = self.engine.get_calendar()
        assert len(calendar) == len(SAMPLE_EVENTS)

        # 验证事件按触发周排序
        trigger_weeks = [e["trigger_week"] for e in calendar]
        assert trigger_weeks == sorted(trigger_weeks)

    def test_weekly_advance(self):
        """每周自动推进1-2个背景事件"""
        for event in SAMPLE_EVENTS:
            self.engine.register_event(event)

        # 推进到第8周
        active_events = self.engine.advance_to_week(8)

        assert isinstance(active_events, list)
        # 第8周及之前应有触发的事件
        assert len(active_events) >= 1
        # 验证触发了"秋风渐起"和"江湖传闻"
        event_ids = [e["id"] for e in active_events]
        assert "season_autumn" in event_ids
        assert "rumor_spread" in event_ids

    def test_information_permeation(self):
        """信息渗透机制：事件→描写片段转化"""
        self.engine.register_event(SAMPLE_EVENTS[0])  # 秋风渐起
        self.engine.advance_to_week(8)

        snippet = self.engine.generate_permeation_snippet(
            event_id="season_autumn",
            scene_context="你走在山间小路上",
        )

        assert isinstance(snippet, str)
        assert len(snippet) > 0
        # 描写片段应融入场景而非生硬插入
        assert len(snippet) < 500

    def test_event_types(self):
        """事件类型：季节变化、市场波动、政治动荡、自然灾害、流言传播"""
        valid_types = {"季节变化", "市场波动", "政治动荡", "自然灾害", "流言传播"}

        for event in SAMPLE_EVENTS:
            self.engine.register_event(event)
            assert event["type"] in valid_types

        # 引擎应能按类型筛选
        seasonal = self.engine.get_events_by_type("季节变化")
        assert len(seasonal) >= 1
        assert all(e["type"] == "季节变化" for e in seasonal)

    def test_style_chinese_classic(self):
        """中国古典=江湖传闻/官府告示"""
        for event in SAMPLE_EVENTS:
            self.engine.register_event(event)

        self.engine.advance_to_week(6)
        snippet = self.engine.generate_permeation_snippet(
            event_id="rumor_spread",
            scene_context="你在茶馆喝茶",
            style="chinese_classic",
        )

        assert isinstance(snippet, str)
        # 中国古典风格应有江湖气息
        assert len(snippet) > 0

    def test_style_western_fantasy(self):
        """西方奇幻=预言/旅人传说"""
        for event in WESTERN_EVENTS:
            self.engine.register_event(event)

        self.engine.advance_to_week(7)
        snippet = self.engine.generate_permeation_snippet(
            event_id="traveler_tale",
            scene_context="你在酒馆歇脚",
            style="western_fantasy",
        )

        assert isinstance(snippet, str)
        assert len(snippet) > 0

    def test_degradation(self):
        """异常时优雅降级"""
        # 空日历推进不崩溃
        result = self.engine.advance_to_week(10)
        assert isinstance(result, list)

        # 不存在的事件ID不崩溃
        snippet = self.engine.generate_permeation_snippet(
            event_id="nonexistent",
            scene_context="任意场景",
        )
        assert isinstance(snippet, str)

        # None 输入不崩溃
        self.engine.register_event(None)  # 应静默忽略
