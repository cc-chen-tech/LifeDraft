"""Tests for PromptEnhancer - 自适应提示词增强器测试

测试根据反馈优化提示词，学习用户反馈历史自动增强提示词以提高生成质量。
"""

import os
import tempfile
from datetime import datetime

from src.services.image.prompt_enhancer import (
    EnhancementRule,
    PromptEnhancer,
    PromptFeedback,
    prompt_enhancer,
)


class TestPromptFeedback:
    """提示词反馈记录测试"""

    def test_create_feedback(self):
        """测试创建反馈"""
        feedback = PromptFeedback(
            image_id=1,
            feedback_text="人物不像",
            is_positive=False,
            timestamp=datetime.utcnow(),
            character_name="测试角色",
        )

        assert feedback.image_id == 1
        assert feedback.feedback_text == "人物不像"
        assert feedback.is_positive is False
        assert feedback.character_name == "测试角色"


class TestEnhancementRule:
    """增强规则测试"""

    def test_create_rule(self):
        """测试创建规则"""
        rule = EnhancementRule(
            trigger_keywords=["不像", "变了"],
            enhancement_text="保持人物一致性",
            priority=10,
        )

        assert len(rule.trigger_keywords) == 2
        assert rule.enhancement_text == "保持人物一致性"
        assert rule.priority == 10
        assert rule.apply_count == 0
        assert rule.success_count == 0


class TestPromptEnhancerInit:
    """增强器初始化测试"""

    def test_init_with_defaults(self):
        """测试默认初始化"""
        enhancer = PromptEnhancer()

        assert len(enhancer.rules) == len(PromptEnhancer.DEFAULT_RULES)
        assert enhancer.feedback_history == []
        assert enhancer.character_feedback == {}
        assert enhancer.storage_path is None

    def test_init_with_storage_path(self):
        """测试带存储路径初始化"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            enhancer = PromptEnhancer(storage_path=temp_path)
            assert enhancer.storage_path == temp_path
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_default_rules_loaded(self):
        """测试默认规则已加载"""
        enhancer = PromptEnhancer()

        # 验证默认规则存在
        keywords = []
        for rule in enhancer.rules:
            keywords.extend(rule.trigger_keywords)

        assert "不像" in keywords
        assert "模糊" in keywords
        assert "光线" in keywords


class TestRecordFeedback:
    """反馈记录测试"""

    def test_record_feedback_basic(self):
        """测试基本反馈记录"""
        enhancer = PromptEnhancer()

        enhancer.record_feedback(
            image_id=1,
            character_name="测试角色",
            feedback_text="人物不像",
            is_positive=False,
        )

        assert len(enhancer.feedback_history) == 1
        assert len(enhancer.character_feedback["测试角色"]) == 1

    def test_record_multiple_feedbacks_same_character(self):
        """测试同一角色多条反馈"""
        enhancer = PromptEnhancer()

        enhancer.record_feedback(
            image_id=1,
            character_name="测试角色",
            feedback_text="人物不像",
            is_positive=False,
        )
        enhancer.record_feedback(
            image_id=2,
            character_name="测试角色",
            feedback_text="还是不像",
            is_positive=False,
        )

        assert len(enhancer.feedback_history) == 2
        assert len(enhancer.character_feedback["测试角色"]) == 2

    def test_record_feedback_different_characters(self):
        """测试不同角色反馈"""
        enhancer = PromptEnhancer()

        enhancer.record_feedback(
            image_id=1,
            character_name="角色A",
            feedback_text="不像",
            is_positive=False,
        )
        enhancer.record_feedback(
            image_id=2,
            character_name="角色B",
            feedback_text="很好",
            is_positive=True,
        )

        assert len(enhancer.character_feedback) == 2
        assert "角色A" in enhancer.character_feedback
        assert "角色B" in enhancer.character_feedback

    def test_positive_feedback_updates_rule_stats(self):
        """测试正面反馈更新规则统计"""
        enhancer = PromptEnhancer()

        # 记录正面反馈，触发"不像"规则
        enhancer.record_feedback(
            image_id=1,
            character_name="测试角色",
            feedback_text="现在不像的问题了，人物很一致",
            is_positive=True,
        )

        # 找到对应的规则并验证成功计数增加
        for rule in enhancer.rules:
            if "不像" in rule.trigger_keywords:
                assert rule.success_count > 0


class TestEnhancePrompt:
    """提示词增强测试"""

    def test_enhance_no_feedback(self):
        """测试无反馈时的增强"""
        enhancer = PromptEnhancer()

        base_prompt = "生成一个人物"
        enhanced = enhancer.enhance(base_prompt)

        # 没有反馈时，应添加通用增强
        assert "增强要求" in enhanced
        assert "人物生成质量要求" in enhanced

    def test_enhance_with_character_feedback(self):
        """测试有角色反馈时的增强"""
        enhancer = PromptEnhancer()

        # 记录负面反馈
        enhancer.record_feedback(
            image_id=1,
            character_name="测试角色",
            feedback_text="人物不像，变了",
            is_positive=False,
        )

        base_prompt = "生成测试角色"
        enhanced = enhancer.enhance(base_prompt, character_name="测试角色")

        # 应包含一致性相关的增强
        assert "增强要求" in enhanced
        # 包含 "严格要求" 头部或具体的一致性要求文本
        assert (
            "严格要求" in enhanced or "保持一致" in enhanced or "五官比例" in enhanced
        )

    def test_enhance_multiple_negative_feedback(self):
        """测试多条负面反馈时的增强"""
        enhancer = PromptEnhancer()

        # 记录多条负面反馈
        for i in range(3):
            enhancer.record_feedback(
                image_id=i,
                character_name="测试角色",
                feedback_text="不像",
                is_positive=False,
            )

        base_prompt = "生成测试角色"
        enhanced = enhancer.enhance(base_prompt, character_name="测试角色")

        # 应包含严格约束
        assert "重要" in enhanced or "严格" in enhanced

    def test_enhance_scene_type(self):
        """测试场景类型增强"""
        enhancer = PromptEnhancer()

        base_prompt = "生成场景"
        enhanced = enhancer.enhance(base_prompt, image_type="scene")

        # 应包含场景生成质量要求
        assert "场景生成质量要求" in enhanced
        assert "电影感" in enhanced


class TestGetCharacterQualityScore:
    """角色质量评分测试"""

    def test_no_feedback_default_score(self):
        """测试无反馈时默认满分"""
        enhancer = PromptEnhancer()

        score = enhancer.get_character_quality_score("新角色")

        assert score == 1.0

    def test_all_positive_score(self):
        """测试全正面反馈得分"""
        enhancer = PromptEnhancer()

        for i in range(5):
            enhancer.record_feedback(
                image_id=i,
                character_name="测试角色",
                feedback_text="很好",
                is_positive=True,
            )

        score = enhancer.get_character_quality_score("测试角色")

        assert score == 1.0

    def test_all_negative_score(self):
        """测试全负面反馈得分"""
        enhancer = PromptEnhancer()

        for i in range(5):
            enhancer.record_feedback(
                image_id=i,
                character_name="测试角色",
                feedback_text="不像",
                is_positive=False,
            )

        score = enhancer.get_character_quality_score("测试角色")

        assert score == 0.0

    def test_mixed_feedback_score(self):
        """测试混合反馈得分"""
        enhancer = PromptEnhancer()

        # 3正面，2负面
        for i in range(3):
            enhancer.record_feedback(
                image_id=i,
                character_name="测试角色",
                feedback_text="很好",
                is_positive=True,
            )
        for i in range(3, 5):
            enhancer.record_feedback(
                image_id=i,
                character_name="测试角色",
                feedback_text="不像",
                is_positive=False,
            )

        score = enhancer.get_character_quality_score("测试角色")

        assert score == 0.6  # 3/5


class TestShouldIncreaseConstraints:
    """增加约束判断测试"""

    def test_high_quality_no_constraints(self):
        """测试高质量不需要增加约束"""
        enhancer = PromptEnhancer()

        # 全正面反馈
        for i in range(5):
            enhancer.record_feedback(
                image_id=i,
                character_name="好角色",
                feedback_text="很好",
                is_positive=True,
            )

        assert enhancer.should_increase_constraints("好角色") is False

    def test_low_quality_needs_constraints(self):
        """测试低质量需要增加约束"""
        enhancer = PromptEnhancer()

        # 全负面反馈
        for i in range(5):
            enhancer.record_feedback(
                image_id=i,
                character_name="差角色",
                feedback_text="不像",
                is_positive=False,
            )

        assert enhancer.should_increase_constraints("差角色") is True

    def test_borderline_quality(self):
        """测试边界质量"""
        enhancer = PromptEnhancer()

        # 60%正面，刚好在阈值上
        for i in range(6):
            enhancer.record_feedback(
                image_id=i,
                character_name="边界角色",
                feedback_text="很好",
                is_positive=True,
            )
        for i in range(6, 10):
            enhancer.record_feedback(
                image_id=i,
                character_name="边界角色",
                feedback_text="不像",
                is_positive=False,
            )

        # 60% >= 60%，不需要增加约束
        assert enhancer.should_increase_constraints("边界角色") is False

        # 添加一条负面，变成55%
        enhancer.record_feedback(
            image_id=10,
            character_name="边界角色",
            feedback_text="不像",
            is_positive=False,
        )

        # 现在需要增加约束
        assert enhancer.should_increase_constraints("边界角色") is True


class TestRuleMatching:
    """规则匹配测试"""

    def test_match_rules_basic(self):
        """测试基本规则匹配"""
        enhancer = PromptEnhancer()

        matched = enhancer._match_rules("人物不像，变了")

        # 应匹配"不像"规则
        assert len(matched) > 0
        keywords = []
        for rule in matched:
            keywords.extend(rule.trigger_keywords)
        assert "不像" in keywords

    def test_match_rules_multiple(self):
        """测试多规则匹配"""
        enhancer = PromptEnhancer()

        matched = enhancer._match_rules("人物不像，而且光线太暗")

        # 应匹配多条规则
        keywords = []
        for rule in matched:
            keywords.extend(rule.trigger_keywords)

        assert "不像" in keywords or "变了" in keywords
        assert "光线" in keywords or "太暗" in keywords

    def test_match_rules_priority(self):
        """测试规则优先级排序"""
        enhancer = PromptEnhancer()

        matched = enhancer._match_rules("不像，光线问题")

        # 按优先级排序，高优先级在前
        if len(matched) >= 2:
            assert matched[0].priority >= matched[1].priority

    def test_match_rules_limit(self):
        """测试规则数量限制"""
        enhancer = PromptEnhancer()

        # 包含多个关键词
        matched = enhancer._match_rules(
            "不像，模糊，光线太暗，表情不像，服装不对，姿势僵硬"
        )

        # 最多返回3条规则
        assert len(matched) <= 3


class TestRecentFeedback:
    """最近反馈获取测试"""

    def test_get_recent_feedback_limit(self):
        """测试最近反馈数量限制"""
        enhancer = PromptEnhancer()

        # 添加10条反馈
        for i in range(10):
            enhancer.record_feedback(
                image_id=i,
                character_name="测试角色",
                feedback_text=f"反馈{i}",
                is_positive=False,
            )

        recent = enhancer._get_recent_feedback("测试角色", limit=5)

        assert len(recent) == 5

    def test_get_recent_feedback_order(self):
        """测试最近反馈时间顺序"""
        enhancer = PromptEnhancer()

        # 按顺序添加反馈
        for i in range(5):
            enhancer.record_feedback(
                image_id=i,
                character_name="测试角色",
                feedback_text=f"反馈{i}",
                is_positive=False,
            )

        recent = enhancer._get_recent_feedback("测试角色", limit=3)

        # 应该是最近的3条（反馈2, 3, 4）
        assert len(recent) == 3
        # 验证时间倒序
        for i in range(len(recent) - 1):
            assert recent[i].timestamp >= recent[i + 1].timestamp


class TestStats:
    """统计信息测试"""

    def test_get_stats(self):
        """测试获取统计信息"""
        enhancer = PromptEnhancer()

        # 添加一些反馈
        enhancer.record_feedback(
            image_id=1,
            character_name="角色A",
            feedback_text="不像",
            is_positive=False,
        )
        enhancer.record_feedback(
            image_id=2,
            character_name="角色B",
            feedback_text="很好",
            is_positive=True,
        )

        stats = enhancer.get_stats()

        assert stats["total_feedback"] == 2
        assert stats["characters_tracked"] == 2
        assert stats["rules_count"] == len(enhancer.rules)
        assert len(stats["top_rules"]) <= 5


class TestPersistence:
    """持久化测试"""

    def test_save_and_load_rules(self):
        """测试规则保存和加载"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            # 创建增强器并添加自定义规则
            enhancer1 = PromptEnhancer(storage_path=temp_path)
            custom_rule = EnhancementRule(
                trigger_keywords=["测试关键词"],
                enhancement_text="测试增强",
                priority=5,
            )
            enhancer1.rules.append(custom_rule)
            enhancer1.save_rules()

            # 创建新的增强器加载规则
            enhancer2 = PromptEnhancer(storage_path=temp_path)

            # 验证自定义规则已加载
            found = False
            for rule in enhancer2.rules:
                if "测试关键词" in rule.trigger_keywords:
                    found = True
                    break
            assert found

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestGlobalEnhancer:
    """全局增强器实例测试"""

    def test_global_instance_exists(self):
        """测试全局实例存在"""
        assert isinstance(prompt_enhancer, PromptEnhancer)

    def test_global_instance_has_rules(self):
        """测试全局实例包含默认规则"""
        assert len(prompt_enhancer.rules) > 0
